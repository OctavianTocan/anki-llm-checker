"""Push card-template-front.html to Anki's database.

Reads the template source file and writes it into the protobuf blob
in collection.anki2. This replaces all incremental patch scripts —
edit the HTML file, run this, restart Anki.

Usage: Close Anki, then run: python3 push-template.py
"""

import sqlite3
import os

DB = os.path.expanduser(
    "~/Library/Application Support/Anki2/User 1/collection.anki2"
)
NTID = 1774621368457
TEMPLATE = os.path.join(os.path.dirname(__file__), "card-template-front.html")


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


with open(TEMPLATE) as f:
    new_html = f.read()

db = sqlite3.connect(DB)
blob = db.execute(
    "SELECT config FROM templates WHERE ntid = ? AND ord = 0", (NTID,)
).fetchone()[0]

fields = parse_fields(blob)
old_html = fields[0][2].decode('utf-8')

if old_html == new_html:
    print("Template already up to date — skipping.")
    db.close()
    exit(0)

fields[0] = (1, 2, new_html.encode('utf-8'))
new_blob = encode_fields(fields)

db.execute(
    "UPDATE templates SET config = ? WHERE ntid = ? AND ord = 0",
    (new_blob, NTID),
)
db.commit()
db.close()

old_size = len(old_html)
new_size = len(new_html)
print(f"Template pushed ({old_size:,} → {new_size:,} bytes). Open Anki to verify.")
