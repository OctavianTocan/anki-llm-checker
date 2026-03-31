"""Hide the textarea scrollbar and add gradient fade overlays.

Two polish items:
1. Hide the visible scrollbar on the textarea (ugly gray bar in QtWebEngine).
2. Add top/bottom gradient fades when the textarea is scrollable, so text
   blends at the edges like a chat input.

The gradient overlays use ::before / ::after pseudo-elements on the wrapper,
driven by a `.scrollable` CSS class that the oninput handler toggles. The
gradients go from var(--llm-bg) to transparent so they work in both light
and dark mode automatically.

Usage: Close Anki, then run: python3 patch-scrollbar-fade.py
"""

import sqlite3
import os

DB = os.path.expanduser(
    "~/Library/Application Support/Anki2/User 1/collection.anki2"
)
NTID = 1774621368457


def decode_varint(data, pos):
    """Decode a protobuf varint starting at pos, return (value, new_pos)."""
    value = 0; shift = 0
    while True:
        b = data[pos]; pos += 1
        value |= (b & 0x7F) << shift; shift += 7
        if not (b & 0x80): break
    return value, pos


def encode_varint(value):
    """Encode an integer as a protobuf varint."""
    out = bytearray()
    while value > 0x7F:
        out.append((value & 0x7F) | 0x80); value >>= 7
    out.append(value & 0x7F)
    return bytes(out)


def parse_fields(data):
    """Parse protobuf wire format into a list of (field_num, wire_type, content)."""
    fields = []; i = 0
    while i < len(data):
        tag_byte = data[i]; fn = tag_byte >> 3; wt = tag_byte & 7; i += 1
        if wt == 2:
            length, i = decode_varint(data, i)
            fields.append((fn, wt, data[i:i+length])); i += length
        elif wt == 0:
            val, i = decode_varint(data, i)
            fields.append((fn, wt, val))
    return fields


def encode_fields(fields):
    """Re-encode parsed protobuf fields back to binary."""
    out = bytearray()
    for fn, wt, c in fields:
        out.append((fn << 3) | wt)
        if wt == 2: out.extend(encode_varint(len(c))); out.extend(c)
        elif wt == 0: out.extend(encode_varint(c))
    return bytes(out)


def patch(html):
    """Add scrollbar hiding and gradient fade overlays to the textarea input.

    Changes:
    1. CSS: Hide scrollbar on #llm-input via ::-webkit-scrollbar and
       scrollbar-width: none.
    2. CSS: Add position: relative + overflow: hidden to #llm-input-wrap
       so pseudo-elements are contained within the border-radius.
    3. CSS: Add ::before / ::after gradient overlays on #llm-input-wrap
       that only appear when the .scrollable class is present.
    4. JS: Update oninput handler to toggle the .scrollable class on the
       wrapper based on whether the textarea content overflows.
    """

    # 1. Hide the scrollbar — add rules after the existing #llm-input block.
    #    Insert right before #llm-input::placeholder.
    old_placeholder = '#llm-input::placeholder { color: var(--llm-text-faint); }'
    new_placeholder = (
        '/* Hide scrollbar while keeping scroll functional */\n'
        '#llm-input::-webkit-scrollbar { display: none; }\n'
        '#llm-input { scrollbar-width: none; }\n'
        '#llm-input::placeholder { color: var(--llm-text-faint); }'
    )
    html = html.replace(old_placeholder, new_placeholder)

    # 2. Add position: relative + overflow: hidden to #llm-input-wrap
    #    so the pseudo-element gradients clip to the border-radius.
    old_wrap = (
        '#llm-input-wrap {\n'
        '  display: flex; align-items: flex-end;\n'
        '  border-radius: 16px;\n'
        '  border: 1px solid var(--llm-border); background: var(--llm-bg);'
    )
    new_wrap = (
        '#llm-input-wrap {\n'
        '  position: relative; overflow: hidden;\n'
        '  display: flex; align-items: flex-end;\n'
        '  border-radius: 16px;\n'
        '  border: 1px solid var(--llm-border); background: var(--llm-bg);'
    )
    html = html.replace(old_wrap, new_wrap)

    # 3. Add the gradient overlay CSS — insert right before
    #    the #llm-input-wrap:hover rule.
    old_hover = '#llm-input-wrap:hover { border-color: var(--llm-border-hover);'
    new_hover = (
        '/* Gradient fade overlays — only visible when textarea is scrollable */\n'
        '#llm-input-wrap::before,\n'
        '#llm-input-wrap::after {\n'
        '  content: ""; position: absolute; left: 0; right: 0;\n'
        '  height: 14px; pointer-events: none; z-index: 1;\n'
        '  opacity: 0; transition: opacity 0.15s ease;\n'
        '}\n'
        '#llm-input-wrap::before {\n'
        '  top: 0;\n'
        '  background: linear-gradient(to bottom, var(--llm-bg), transparent);\n'
        '  border-radius: 16px 16px 0 0;\n'
        '}\n'
        '#llm-input-wrap::after {\n'
        '  bottom: 0;\n'
        '  background: linear-gradient(to top, var(--llm-bg), transparent);\n'
        '  border-radius: 0 0 16px 16px;\n'
        '}\n'
        '#llm-input-wrap.scrollable::before,\n'
        '#llm-input-wrap.scrollable::after {\n'
        '  opacity: 1;\n'
        '}\n'
        '#llm-input-wrap:hover { border-color: var(--llm-border-hover);'
    )
    html = html.replace(old_hover, new_hover)

    # 4. Update oninput handler to also toggle .scrollable on the wrapper.
    #    The class is added when scrollHeight exceeds the max-height (160px).
    old_oninput = (
        "oninput=\"this.style.height='auto';"
        "var h=Math.min(this.scrollHeight,160);"
        "this.style.height=h+'px';"
        "this.style.overflowY=this.scrollHeight>160?'auto':'hidden';\""
    )
    new_oninput = (
        "oninput=\"this.style.height='auto';"
        "var h=Math.min(this.scrollHeight,160);"
        "this.style.height=h+'px';"
        "this.style.overflowY=this.scrollHeight>160?'auto':'hidden';"
        "this.parentElement.classList.toggle('scrollable',this.scrollHeight>160);\""
    )
    html = html.replace(old_oninput, new_oninput)

    return html


# -- Main --
db = sqlite3.connect(DB, timeout=10)
blob = db.execute(
    "SELECT config FROM templates WHERE ntid = ? AND ord = 0", (NTID,)
).fetchone()[0]

fields = parse_fields(blob)
old_html = fields[0][2].decode('utf-8')
new_html = patch(old_html)

if old_html == new_html:
    print("ERROR: No changes detected — check string matching.")
    db.close()
    exit(1)

fields[0] = (1, 2, new_html.encode('utf-8'))
db.execute(
    "UPDATE templates SET config = ? WHERE ntid = ? AND ord = 0",
    (encode_fields(fields), NTID),
)
db.commit()
db.close()
print("Applied: hidden scrollbar + gradient fade overlays.")
print("Open Anki to verify.")
