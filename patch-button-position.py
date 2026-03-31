"""Fix send button appearing outside the input container border.

The button uses position: absolute inside a position: relative wrapper,
but in Anki's QtWebEngine the button renders outside the border. Fix by
switching to flexbox layout so the button is part of the normal flow and
always contained within the wrapper's border.

Usage: Close Anki, then run: python3 patch-button-position.py
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
    """Replace absolute-positioned button with flexbox layout.

    Root cause: position: absolute on #llm-send places the button outside
    the wrapper's visible border in QtWebEngine. Flexbox keeps the button
    in normal flow, always inside the border.
    """

    # 1. Fix #llm-input-wrap: replace position: relative with flexbox
    old_wrap = (
        "#llm-input-wrap {\n"
        "  position: relative; border-radius: 16px;\n"
        "  border: 1px solid var(--llm-border); background: var(--llm-bg);\n"
        "  box-shadow: var(--llm-shadow);\n"
        "  transition: border-color 0.2s ease, background 0.2s ease, box-shadow 0.2s ease;\n"
        "}"
    )
    new_wrap = (
        "#llm-input-wrap {\n"
        "  display: flex; align-items: flex-end;\n"
        "  border-radius: 16px;\n"
        "  border: 1px solid var(--llm-border); background: var(--llm-bg);\n"
        "  box-shadow: var(--llm-shadow);\n"
        "  transition: border-color 0.2s ease, background 0.2s ease, box-shadow 0.2s ease;\n"
        "}"
    )
    html = html.replace(old_wrap, new_wrap)

    # 2. Fix #llm-input: remove right padding hack (was reserving space
    #    for the absolute button), let flexbox handle the layout instead.
    #    Also use flex: 1 so the textarea fills remaining width.
    old_input = (
        "#llm-input {\n"
        "  display: block; width: 100%; min-height: 44px; max-height: 160px;\n"
        "  padding: 10px 44px 10px 16px; box-sizing: border-box;\n"
        "  border: none; background: transparent;"
    )
    new_input = (
        "#llm-input {\n"
        "  flex: 1; min-width: 0; min-height: 44px; max-height: 160px;\n"
        "  padding: 10px 0 10px 16px; box-sizing: border-box;\n"
        "  border: none; background: transparent;"
    )
    html = html.replace(old_input, new_input)

    # 3. Fix #llm-send: remove absolute positioning, use flex-none with
    #    margin to pin it at bottom-right inside the wrapper.
    old_send = (
        "#llm-send {\n"
        "  position: absolute; bottom: 8px; right: 8px;\n"
        "  width: 28px; height: 28px; padding: 0;\n"
        "  display: flex; align-items: center; justify-content: center;"
    )
    new_send = (
        "#llm-send {\n"
        "  flex: none; margin: 0 8px 8px 4px;\n"
        "  width: 28px; height: 28px; padding: 0;\n"
        "  display: flex; align-items: center; justify-content: center;"
    )
    html = html.replace(old_send, new_send)

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
print("Fixed: send button now uses flexbox layout (inside the border).")
print("Open Anki to verify.")
