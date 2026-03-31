"""Fix textarea empty-state height and scroll behavior.

Two bugs:
1. No rows="1" on textarea — browser defaults to rows=2, making it ~70px
   tall even though CSS says min-height: 44px.
2. overflow-y: hidden — clips text when textarea hits max-height (160px),
   user can't scroll.

Usage: Close Anki, then run: python3 patch-input-fix.py
"""

import sqlite3
import os

DB = os.path.expanduser(
    "~/Library/Application Support/Anki2/User 1/collection.anki2"
)
NTID = 1774621368457


def decode_varint(data, pos):
    value = 0; shift = 0
    while True:
        b = data[pos]; pos += 1
        value |= (b & 0x7F) << shift; shift += 7
        if not (b & 0x80): break
    return value, pos


def encode_varint(value):
    out = bytearray()
    while value > 0x7F:
        out.append((value & 0x7F) | 0x80); value >>= 7
    out.append(value & 0x7F)
    return bytes(out)


def parse_fields(data):
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
    out = bytearray()
    for fn, wt, c in fields:
        out.append((fn << 3) | wt)
        if wt == 2: out.extend(encode_varint(len(c))); out.extend(c)
        elif wt == 0: out.extend(encode_varint(c))
    return bytes(out)


def patch(html):
    # 1. Add rows="1" to textarea so browser doesn't default to rows=2
    html = html.replace(
        '<textarea id="llm-input" placeholder="Describe your approach..."',
        '<textarea id="llm-input" rows="1" placeholder="Describe your approach..."',
    )

    # 2. Update oninput handler to toggle overflow-y when at max-height
    old_oninput = (
        "oninput=\"this.style.height='auto';"
        "this.style.height=Math.min(this.scrollHeight,160)+'px';\""
    )
    new_oninput = (
        "oninput=\"this.style.height='auto';"
        "var h=Math.min(this.scrollHeight,160);"
        "this.style.height=h+'px';"
        "this.style.overflowY=this.scrollHeight>160?'auto':'hidden';\""
    )
    html = html.replace(old_oninput, new_oninput)

    return html


# ── Main ──
db = sqlite3.connect(DB)
blob = db.execute(
    "SELECT config FROM templates WHERE ntid = ? AND ord = 0", (NTID,)
).fetchone()[0]

fields = parse_fields(blob)
old_html = fields[0][2].decode('utf-8')
new_html = patch(old_html)

if old_html == new_html:
    print("No changes detected — check string matching.")
    db.close()
    exit(1)

fields[0] = (1, 2, new_html.encode('utf-8'))
db.execute(
    "UPDATE templates SET config = ? WHERE ntid = ? AND ord = 0",
    (encode_fields(fields), NTID),
)
db.commit()
db.close()
print("Fixed: rows=1 + scroll overflow. Open Anki to verify.")
