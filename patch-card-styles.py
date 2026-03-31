"""Add card-level typography to match the LLM checker section.

Usage: Close Anki, then run: python3 patch-card-styles.py
"""

import sqlite3
import os

DB = os.path.expanduser(
    "~/Library/Application Support/Anki2/User 1/collection.anki2"
)
NTID = 1774621368457

CARD_CSS = """
/* ── Card-level typography ── */
.card {
  font-family: -apple-system, "SF Pro Text", system-ui, sans-serif;
  color: var(--llm-text);
  line-height: 1.65;
  letter-spacing: -0.008em;
  -webkit-font-smoothing: antialiased;
}
h1 {
  font-size: 11.5px; font-weight: 500; letter-spacing: 0.02em;
  color: var(--llm-text-muted); margin: 0 0 12px; text-transform: uppercase;
}
code {
  font-family: "SF Mono", ui-monospace, "Cascadia Code", monospace;
  font-size: 0.86em; padding: 1.5px 5px; border-radius: 4px;
  background: var(--llm-btn-bg); border: 1px solid var(--llm-border);
}
ul, ol { padding-left: 20px; margin: 10px 0; }
li { margin: 3px 0; line-height: 1.6; }
strong { font-weight: 600; color: var(--llm-text); }
"""


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


db = sqlite3.connect(DB)
blob = db.execute(
    "SELECT config FROM templates WHERE ntid = ? AND ord = 0", (NTID,)
).fetchone()[0]

fields = parse_fields(blob)
html = fields[0][2].decode('utf-8')

if 'Card-level typography' in html:
    print("Card styles already present — skipping.")
    db.close()
    exit(0)

# Insert card CSS right after the opening <style> + :root block's first line
html = html.replace(
    '<style>\n:root {',
    '<style>\n' + CARD_CSS + '\n:root {',
)

fields[0] = (1, 2, html.encode('utf-8'))
new_blob = encode_fields(fields)

db.execute(
    "UPDATE templates SET config = ? WHERE ntid = ? AND ord = 0",
    (new_blob, NTID),
)
db.commit()
db.close()
print("Card typography styles added. Open Anki to verify.")
