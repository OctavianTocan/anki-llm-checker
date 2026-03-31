"""Unify card template with a proper design system.

Replaces scattered CSS with a consistent system: shared section labels,
constrained max-width, proper typography scale, and visual separators.

Usage: Close Anki, then run: python3 patch-design-system.py
"""

import sqlite3
import os
import re

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


# ─── Design System CSS ───
# Replaces the old "Card-level typography" block.
# Uses the existing --llm-* tokens for color consistency.

DESIGN_CSS = """\
/* ── Design System ─────────────────────────────────────
   Spacing : 4 · 8 · 12 · 16 · 20 · 24 · 32
   Radius  : 5 · 8 · 12
   Type    : 11.5 · 12 · 13 · 14.5
   ────────────────────────────────────────────────────── */

/* Base */
.card {
  font-family: -apple-system, "SF Pro Text", system-ui, sans-serif;
  color: var(--llm-text);
  font-size: 14.5px;
  line-height: 1.65;
  letter-spacing: -0.008em;
  -webkit-font-smoothing: antialiased;
  max-width: 620px;
  margin: 0 auto;
}

/* Section labels — shared pattern for Problem + Check */
.section-label {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
  font-size: 11.5px;
  font-weight: 500;
  letter-spacing: 0.01em;
  color: var(--llm-text-muted);
}
.section-label svg {
  width: 13px; height: 13px;
  stroke: currentColor; fill: none;
  stroke-width: 1.5; stroke-linecap: round; stroke-linejoin: round;
}

/* Typography */
strong { font-weight: 600; color: var(--llm-text); }
code {
  font-family: "SF Mono", ui-monospace, "Cascadia Code", monospace;
  font-size: 0.86em; padding: 1.5px 6px; border-radius: 5px;
  background: var(--llm-btn-bg); border: 1px solid var(--llm-border);
}
ul, ol { padding-left: 20px; margin: 8px 0; }
li { margin: 4px 0; line-height: 1.6; color: var(--llm-text-soft); }

/* LeetCode link */
#lc-link {
  display: inline-block; margin-top: 16px;
  font-size: 12px; font-weight: 500; letter-spacing: -0.01em;
  color: var(--llm-text-muted); cursor: pointer;
  transition: color 0.15s ease; text-decoration: none;
}
#lc-link:hover { color: var(--llm-text-soft); }

"""


def patch(html):
    # ── 1. Replace <h1> with section-label div ──
    html = html.replace(
        '<h1>Description</h1>',
        '<div class="section-label">\n'
        '  <svg viewBox="0 0 24 24">'
        '<path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/>'
        '<path d="M13 2v7h7"/>'
        '</svg>\n'
        '  Problem\n'
        '</div>',
    )

    # ── 2. Make #llm-label use the shared class ──
    html = html.replace(
        '<div id="llm-label">',
        '<div id="llm-label" class="section-label">',
    )

    # ── 3. Remove old Card-level typography CSS ──
    html = re.sub(
        r'/\* ── Card-level typography ── \*/\n.+?\n(?=\n:root)',
        '',
        html,
        flags=re.DOTALL,
    )

    # ── 4. Remove old standalone #lc-link CSS (from update-template.py) ──
    html = re.sub(
        r'\n#lc-link \{[^}]+\}\n#lc-link:hover \{[^}]+\}\n',
        '\n',
        html,
    )

    # ── 5. Insert design system CSS before :root ──
    html = html.replace(
        '<style>\n\n:root',
        '<style>\n' + DESIGN_CSS + ':root',
    )

    # ── 6. Remove max-width + font-family from #llm-strip (card handles it) ──
    #       Add border-top separator instead
    html = html.replace(
        '#llm-strip {\n'
        '  margin: 28px 0 0; max-width: 620px;\n'
        '  font-family: -apple-system, "SF Pro Text", system-ui, sans-serif;\n'
        '}',
        '#llm-strip {\n'
        '  margin: 24px 0 0; padding-top: 20px;\n'
        '  border-top: 1px solid var(--llm-border);\n'
        '}',
    )

    # ── 7. Remove now-redundant #llm-label styles (shared class handles it) ──
    html = re.sub(
        r'#llm-label \{\n'
        r'  display: flex; align-items: center; gap: 6px; margin-bottom: 10px;\n'
        r'  font-size: 11\.5px; font-weight: 500; letter-spacing: 0\.01em; color: var\(--llm-text-muted\);\n'
        r'\}\n'
        r'#llm-label svg \{\n'
        r'  width: 13px; height: 13px; stroke: var\(--llm-text-muted\);\n'
        r'  fill: none; stroke-width: 1\.5; stroke-linecap: round; stroke-linejoin: round;\n'
        r'\}',
        '/* label styles → .section-label */',
        html,
    )

    return html


# ── Main ──

db = sqlite3.connect(DB)
blob = db.execute(
    "SELECT config FROM templates WHERE ntid = ? AND ord = 0", (NTID,)
).fetchone()[0]

fields = parse_fields(blob)
old_html = fields[0][2].decode('utf-8')

if 'Design System' in old_html:
    print("Design system already applied — skipping.")
    db.close()
    exit(0)

new_html = patch(old_html)
fields[0] = (1, 2, new_html.encode('utf-8'))
new_blob = encode_fields(fields)

db.execute(
    "UPDATE templates SET config = ? WHERE ntid = ? AND ord = 0",
    (new_blob, NTID),
)
db.commit()
db.close()
print("Design system applied. Open Anki to verify.")
