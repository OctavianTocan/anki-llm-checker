"""Fix send button icon invisible in dark mode.

The button uses color: var(--llm-bg-hover) for the arrow icon, which
resolves to near-transparent white in dark mode — white icon on white
button. Adds a dark-mode override to use dark icon color.

Usage: Close Anki, then run: python3 patch-send-button-dark.py
"""

import sqlite3
import os

DB = os.path.expanduser(
    "~/Library/Application Support/Anki2/User 1/collection.anki2"
)
NTID = 1774621368457


def decode_varint(data, pos):
    value = 0
    shift = 0
    while True:
        b = data[pos]
        pos += 1
        value |= (b & 0x7F) << shift
        shift += 7
        if not (b & 0x80):
            break
    return value, pos


def encode_varint(value):
    out = bytearray()
    while value > 0x7F:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value & 0x7F)
    return bytes(out)


def parse_fields(data):
    fields = []
    i = 0
    while i < len(data):
        tag_byte = data[i]
        field_num = tag_byte >> 3
        wire_type = tag_byte & 0x07
        i += 1
        if wire_type == 2:
            length, i = decode_varint(data, i)
            content = data[i:i + length]
            fields.append((field_num, wire_type, content))
            i += length
        elif wire_type == 0:
            value, i = decode_varint(data, i)
            fields.append((field_num, wire_type, value))
        else:
            raise ValueError(f"Unsupported wire type {wire_type}")
    return fields


def encode_fields(fields):
    out = bytearray()
    for field_num, wire_type, content in fields:
        tag = (field_num << 3) | wire_type
        out.append(tag)
        if wire_type == 2:
            out.extend(encode_varint(len(content)))
            out.extend(content)
        elif wire_type == 0:
            out.extend(encode_varint(content))
    return bytes(out)


DARK_SEND_RULE = """\
@media (prefers-color-scheme: dark) {
  #llm-send { color: rgba(0, 0, 0, 0.75); }
}"""

ANCHOR = "#llm-send:disabled { opacity: 0.18; cursor: default; transform: none; }"


db = sqlite3.connect(DB)
blob = db.execute(
    "SELECT config FROM templates WHERE ntid = ? AND ord = 0", (NTID,)
).fetchone()[0]

fields = parse_fields(blob)
html = fields[0][2].decode('utf-8')

if "dark) {\n  #llm-send" in html:
    print("Send button dark fix already applied — skipping.")
    db.close()
    exit(0)

if ANCHOR not in html:
    print("Anchor not found — template may have changed. Aborting.")
    db.close()
    exit(1)

html = html.replace(ANCHOR, ANCHOR + "\n" + DARK_SEND_RULE)

fields[0] = (1, 2, html.encode('utf-8'))
new_blob = encode_fields(fields)

db.execute(
    "UPDATE templates SET config = ? WHERE ntid = ? AND ord = 0",
    (new_blob, NTID),
)
db.commit()
db.close()
print("Send button dark mode fix applied. Open Anki to verify.")
