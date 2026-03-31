"""Refine dark mode theme for better readability during study sessions.

Bumps text opacity levels, replaces invisible dark-on-dark shadows with
subtle glows, increases code block / input surface contrast, and shifts
the accent hue slightly warmer.

Usage: Close Anki, then run: python3 patch-dark-theme.py
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


# ── Token replacements: (old, new) ──
# Each pair is an exact substring match inside the dark media query block.
REPLACEMENTS = [
    # Text hierarchy
    ("--llm-text: rgba(255, 255, 255, 0.9);",
     "--llm-text: rgba(255, 255, 255, 0.93);"),
    ("--llm-text-soft: rgba(255, 255, 255, 0.6);",
     "--llm-text-soft: rgba(255, 255, 255, 0.72);"),
    ("--llm-text-muted: rgba(255, 255, 255, 0.3);",
     "--llm-text-muted: rgba(255, 255, 255, 0.44);"),
    ("--llm-text-faint: rgba(255, 255, 255, 0.14);",
     "--llm-text-faint: rgba(255, 255, 255, 0.24);"),
    # Borders
    ("--llm-border: rgba(255, 255, 255, 0.1);",
     "--llm-border: rgba(255, 255, 255, 0.13);"),
    ("--llm-border-hover: rgba(255, 255, 255, 0.18);",
     "--llm-border-hover: rgba(255, 255, 255, 0.22);"),
    ("--llm-border-focus: rgba(99, 140, 255, 0.45);",
     "--llm-border-focus: rgba(115, 148, 255, 0.5);"),
    # Surfaces
    ("--llm-bg: rgba(255, 255, 255, 0.04);",
     "--llm-bg: rgba(255, 255, 255, 0.065);"),
    ("--llm-bg-hover: rgba(255, 255, 255, 0.065);",
     "--llm-bg-hover: rgba(255, 255, 255, 0.085);"),
    # Shadows — kill invisible dark-on-dark, use subtle glows
    ("--llm-shadow: 0 1px 3px rgba(0,0,0,0.2), 0 4px 12px rgba(0,0,0,0.15);",
     "--llm-shadow: none;"),
    ("--llm-shadow-hover: 0 2px 8px rgba(0,0,0,0.25), 0 8px 24px rgba(0,0,0,0.2);",
     "--llm-shadow-hover: 0 0 0 1px rgba(255, 255, 255, 0.06);"),
    ("--llm-shadow-focus: 0 0 0 3px rgba(99, 140, 255, 0.15), 0 2px 8px rgba(0,0,0,0.25);",
     "--llm-shadow-focus: 0 0 0 3px rgba(115, 148, 255, 0.18), 0 0 12px rgba(115, 148, 255, 0.08);"),
    # Result card
    ("--llm-result-bg: rgba(99, 140, 255, 0.05);",
     "--llm-result-bg: rgba(115, 148, 255, 0.07);"),
    ("--llm-result-border: rgba(99, 140, 255, 0.1);",
     "--llm-result-border: rgba(115, 148, 255, 0.15);"),
    ("--llm-result-shadow: 0 1px 4px rgba(0,0,0,0.2);",
     "--llm-result-shadow: none;"),
    # Error
    ("--llm-err-bg: rgba(239, 68, 68, 0.06);",
     "--llm-err-bg: rgba(239, 68, 68, 0.08);"),
    ("--llm-err-border: rgba(239, 68, 68, 0.12);",
     "--llm-err-border: rgba(239, 68, 68, 0.16);"),
    # Code blocks & buttons
    ("--llm-btn-bg: rgba(255, 255, 255, 0.05);",
     "--llm-btn-bg: rgba(255, 255, 255, 0.09);"),
    ("--llm-btn-bg-hover: rgba(99, 140, 255, 0.12);",
     "--llm-btn-bg-hover: rgba(115, 148, 255, 0.14);"),
    ("--llm-btn-border-hover: rgba(99, 140, 255, 0.35);",
     "--llm-btn-border-hover: rgba(115, 148, 255, 0.38);"),
    # Shimmer
    ("--llm-shimmer-a: rgba(255, 255, 255, 0.15);",
     "--llm-shimmer-a: rgba(255, 255, 255, 0.18);"),
    ("--llm-shimmer-b: rgba(99, 140, 255, 0.6);",
     "--llm-shimmer-b: rgba(115, 148, 255, 0.65);"),
    # Verdict badges
    ("--llm-v-again-bg: rgba(239, 68, 68, 0.12);",
     "--llm-v-again-bg: rgba(239, 68, 68, 0.15);"),
    ("--llm-v-hard-bg: rgba(245, 158, 11, 0.12);",
     "--llm-v-hard-bg: rgba(245, 158, 11, 0.15);"),
    ("--llm-v-good-bg: rgba(34, 197, 94, 0.12);",
     "--llm-v-good-bg: rgba(34, 197, 94, 0.15);"),
    ("--llm-v-easy-bg: rgba(99, 140, 255, 0.12);",
     "--llm-v-easy-bg: rgba(115, 148, 255, 0.15);"),
    ("--llm-v-easy: #93b4ff;",
     "--llm-v-easy: #93b4ff;"),
]


def patch(html):
    """Apply each token replacement. Only touches the dark-mode block."""
    patched = html
    applied = 0
    for old, new in REPLACEMENTS:
        if old == new:
            continue
        if old in patched:
            patched = patched.replace(old, new, 1)
            applied += 1
    return patched, applied


# ── Main ──

db = sqlite3.connect(DB)
blob = db.execute(
    "SELECT config FROM templates WHERE ntid = ? AND ord = 0", (NTID,)
).fetchone()[0]

fields = parse_fields(blob)
old_html = fields[0][2].decode('utf-8')

# Idempotency: check if already patched by looking for new text-soft value
if "rgba(255, 255, 255, 0.72)" in old_html:
    print("Dark theme already refined — skipping.")
    db.close()
    exit(0)

new_html, count = patch(old_html)
if count == 0:
    print("No replacements matched — template may have changed. Aborting.")
    db.close()
    exit(1)

fields[0] = (1, 2, new_html.encode('utf-8'))
new_blob = encode_fields(fields)

db.execute(
    "UPDATE templates SET config = ? WHERE ntid = ? AND ord = 0",
    (new_blob, NTID),
)
db.commit()
db.close()
print(f"Dark theme refined ({count} tokens updated). Open Anki to verify.")
