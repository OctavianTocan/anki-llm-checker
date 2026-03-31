"""Patch the live Anki card template to add the LeetCode URL button.

Usage: Close Anki, then run: python3 update-template.py
"""

import sqlite3
import os
import re

DB = os.path.expanduser(
    "~/Library/Application Support/Anki2/User 1/collection.anki2"
)
NTID = 1774621368457


def decode_varint(data, pos):
    """Decode a protobuf varint starting at pos, return (value, new_pos)."""
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
    """Encode an integer as a protobuf varint."""
    out = bytearray()
    while value > 0x7F:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value & 0x7F)
    return bytes(out)


def parse_fields(data):
    """Parse protobuf wire format into a list of (field_num, wire_type, content)."""
    fields = []
    i = 0
    while i < len(data):
        tag_byte = data[i]
        field_num = tag_byte >> 3
        wire_type = tag_byte & 0x07
        i += 1

        if wire_type == 2:  # length-delimited
            length, i = decode_varint(data, i)
            content = data[i:i + length]
            fields.append((field_num, wire_type, content))
            i += length
        elif wire_type == 0:  # varint
            value, i = decode_varint(data, i)
            fields.append((field_num, wire_type, value))
        else:
            raise ValueError(f"Unsupported wire type {wire_type}")
    return fields


def encode_fields(fields):
    """Re-encode parsed protobuf fields back to binary."""
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


# --- Patches to apply ---

LEETCODE_HTML = """
{{#LeetCode URL}}
<span id="lc-url" style="display:none">{{LeetCode URL}}</span>
<a id="lc-link" onclick="openLeetCode()" tabindex="0">Open on LeetCode \u2192</a>
{{/LeetCode URL}}"""

LEETCODE_CSS = """
#lc-link {
  display: inline-block; margin-top: 14px;
  font-family: inherit; font-size: 12.5px; font-weight: 500;
  color: var(--llm-text-muted); cursor: pointer;
  transition: color 0.15s ease; letter-spacing: -0.01em; text-decoration: none;
}
#lc-link:hover { color: var(--llm-text-soft); }
"""

LEETCODE_JS = """
function openLeetCode() {
  var el = document.getElementById('lc-url');
  if (!el) return;
  var anchor = el.querySelector('a');
  var url = anchor ? anchor.href : el.textContent.trim();
  if (url) pycmd('openurl::' + url);
}
"""


def patch_front_template(html):
    """Insert the LeetCode button, CSS, and JS into the front template."""
    # Skip if already patched
    if 'lc-link' in html:
        print("Template already has LeetCode button — skipping.")
        return html

    # 1. Insert button HTML after {{Front}}
    html = html.replace(
        '{{Front}}\n\n<style>',
        '{{Front}}\n' + LEETCODE_HTML + '\n\n<style>',
    )

    # 2. Insert CSS before </style>
    html = html.replace(
        '</style>',
        LEETCODE_CSS + '</style>',
        1,  # only first occurrence
    )

    # 3. Insert JS function at the top of the script block
    html = html.replace(
        '<script>\n',
        '<script>\n' + LEETCODE_JS + '\n',
        1,
    )

    return html


# --- Main ---

db = sqlite3.connect(DB)
row = db.execute(
    "SELECT config FROM templates WHERE ntid = ? AND ord = 0", (NTID,)
).fetchone()

if not row:
    print(f"No template found for ntid={NTID}")
    db.close()
    exit(1)

blob = row[0]
fields = parse_fields(blob)

# Field 1 (index 0) is the front template
field_num, wire_type, content = fields[0]
assert field_num == 1 and wire_type == 2, "Unexpected field layout"

old_html = content.decode('utf-8')
new_html = patch_front_template(old_html)

if new_html == old_html:
    db.close()
    exit(0)

# Replace field 1 content
fields[0] = (1, 2, new_html.encode('utf-8'))
new_blob = encode_fields(fields)

db.execute(
    "UPDATE templates SET config = ? WHERE ntid = ? AND ord = 0",
    (new_blob, NTID),
)
db.commit()
db.close()
print("Patched template with LeetCode button. Open Anki to verify.")
