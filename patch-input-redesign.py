"""Redesign the LLM input to a modern chat-style input.

Removes: section label, bottom bar, enter hint, text button.
Adds: circular send button inside input, cleaner textarea.
Inspired by ChatGPT/Claude/Littlebird input patterns.

Usage: Close Anki, then run: python3 patch-input-redesign.py
"""

import sqlite3
import os
import re

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


# ── New HTML for the LLM strip ──
OLD_HTML = """\
<div id="llm-strip">
  <div id="llm-label" class="section-label">
    <svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
    Check your understanding
  </div>

  <div id="llm-input-wrap">
    <textarea id="llm-input" placeholder="Describe your approach..."
      onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();checkAnswer();}"></textarea>
    <div id="llm-bottom-bar">
      <span id="llm-hint">&crarr; enter</span>
      <button id="llm-send" onclick="checkAnswer()">
        Check <svg viewBox="0 0 24 24"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
      </button>
    </div>
  </div>

  <div id="llm-thinking"><span>Thinking...</span></div>

  <div id="llm-result" style="display:none;">
    <div id="llm-verdict"><span></span></div>
    <div id="llm-body"></div>
  </div>
</div>"""

NEW_HTML = """\
<div id="llm-strip">
  <div id="llm-input-wrap">
    <textarea id="llm-input" placeholder="What\\u2019s your approach?"
      onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();checkAnswer();}"
      oninput="this.style.height='auto';this.style.height=Math.min(this.scrollHeight,160)+'px';"></textarea>
    <button id="llm-send" onclick="checkAnswer()" aria-label="Check">
      <svg viewBox="0 0 24 24"><path d="M12 19V5"/><path d="M5 12l7-7 7 7"/></svg>
    </button>
  </div>

  <div id="llm-thinking"><span>Thinking...</span></div>

  <div id="llm-result" style="display:none;">
    <div id="llm-verdict"><span></span></div>
    <div id="llm-body"></div>
  </div>
</div>"""


# ── New CSS for the input components ──
# Replaces: #llm-strip, #llm-label, #llm-input-wrap, #llm-input,
#           #llm-bottom-bar, #llm-hint, #llm-send

OLD_CSS_STRIP = """\
#llm-strip {
  margin: 24px 0 0; padding-top: 20px;
  border-top: 1px solid var(--llm-border);
}
/* label styles \u2192 .section-label */
#llm-input-wrap {
  display: flex; flex-direction: column; border-radius: 12px;
  border: 1px solid var(--llm-border); background: var(--llm-bg);
  box-shadow: var(--llm-shadow);
  transition: border-color 0.2s ease, background 0.2s ease, box-shadow 0.2s ease;
  overflow: hidden;
}
#llm-input-wrap:hover { border-color: var(--llm-border-hover); box-shadow: var(--llm-shadow-hover); }
#llm-input-wrap:focus-within {
  border-color: var(--llm-border-focus); background: var(--llm-bg-hover);
  box-shadow: var(--llm-shadow-focus);
}
#llm-input {
  display: block; width: 100%; min-height: 64px; max-height: 160px;
  padding: 12px 14px 8px; box-sizing: border-box; border: none; background: transparent;
  color: var(--llm-text); font-family: inherit; font-size: 14px;
  line-height: 1.55; letter-spacing: -0.006em; resize: none; outline: none; overflow-y: auto;
}
#llm-input::placeholder { color: var(--llm-text-faint); }
#llm-bottom-bar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 4px 6px 6px 14px; flex-shrink: 0;
}
#llm-hint { font-size: 11px; color: var(--llm-text-faint); letter-spacing: -0.01em; }
#llm-send {
  display: inline-flex; align-items: center; gap: 4px; height: 26px; padding: 0 10px;
  border: 1px solid var(--llm-border); border-radius: 6px; background: var(--llm-btn-bg);
  color: var(--llm-text-soft); font-family: inherit; font-size: 11.5px;
  font-weight: 500; letter-spacing: -0.01em; cursor: pointer;
  transition: all 0.15s ease; -webkit-user-select: none; user-select: none; flex-shrink: 0;
}
#llm-send:hover {
  border-color: var(--llm-btn-border-hover); color: var(--llm-text);
  background: var(--llm-btn-bg-hover); box-shadow: 0 1px 3px rgba(59,130,246,0.1);
}
#llm-send:active { transform: scale(0.97); opacity: 0.85; }
#llm-send:disabled { opacity: 0.25; cursor: default; transform: none; }
#llm-send svg {
  width: 10px; height: 10px; stroke: currentColor; fill: none;
  stroke-width: 2; stroke-linecap: round; stroke-linejoin: round;
}"""

NEW_CSS_STRIP = """\
#llm-strip {
  margin: 24px 0 0; padding-top: 20px;
  border-top: 1px solid var(--llm-border);
}
#llm-input-wrap {
  position: relative; border-radius: 16px;
  border: 1px solid var(--llm-border); background: var(--llm-bg);
  box-shadow: var(--llm-shadow);
  transition: border-color 0.2s ease, background 0.2s ease, box-shadow 0.2s ease;
}
#llm-input-wrap:hover { border-color: var(--llm-border-hover); box-shadow: var(--llm-shadow-hover); }
#llm-input-wrap:focus-within {
  border-color: var(--llm-border-focus); background: var(--llm-bg-hover);
  box-shadow: var(--llm-shadow-focus);
}
#llm-input {
  display: block; width: 100%; height: 44px; max-height: 160px;
  padding: 11px 48px 11px 16px; box-sizing: border-box;
  border: none; background: transparent;
  color: var(--llm-text); font-family: inherit; font-size: 14px;
  line-height: 1.55; letter-spacing: -0.006em;
  resize: none; outline: none; overflow-y: hidden;
}
#llm-input::placeholder { color: var(--llm-text-faint); }
#llm-send {
  position: absolute; bottom: 8px; right: 8px;
  width: 28px; height: 28px;
  display: flex; align-items: center; justify-content: center;
  border-radius: 50%; border: none;
  background: var(--llm-text); color: var(--llm-bg-hover);
  cursor: pointer;
  transition: opacity 0.15s ease, transform 0.1s ease;
}
#llm-send:hover { opacity: 0.8; }
#llm-send:active { transform: scale(0.9); }
#llm-send:disabled { opacity: 0.18; cursor: default; transform: none; }
#llm-send svg {
  width: 14px; height: 14px; stroke: currentColor; fill: none;
  stroke-width: 2; stroke-linecap: round; stroke-linejoin: round;
}"""


# ── JS changes: remove text-based button reset ──
OLD_JS_ARROW = """var _llmArrowSvg = '<svg viewBox="0 0 24 24" width="10" height="10" stroke="currentColor" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M12 5l7 7-7 7"/></svg>';"""

OLD_JS_CHECK_BTN = """  var btn = document.getElementById('llm-send');
  btn.disabled = true;
  btn.textContent = 'Checking\u2026';"""

NEW_JS_CHECK_BTN = """  var btn = document.getElementById('llm-send');
  btn.disabled = true;"""

OLD_JS_RESET = """function _llmReset() {
  var btn = document.getElementById('llm-send');
  if (!btn) return;
  btn.disabled = false;
  btn.innerHTML = (_llmHasChecked ? 'Check again ' : 'Check ') + _llmArrowSvg;
}"""

NEW_JS_RESET = """function _llmReset() {
  var btn = document.getElementById('llm-send');
  if (btn) btn.disabled = false;
}"""


def patch(html):
    # 1. Replace HTML structure
    html = html.replace(OLD_HTML, NEW_HTML)

    # 2. Replace CSS
    html = html.replace(OLD_CSS_STRIP, NEW_CSS_STRIP)

    # 3. Replace JS
    html = html.replace(OLD_JS_ARROW + '\n', '')  # remove arrow SVG var
    html = html.replace(OLD_JS_CHECK_BTN, NEW_JS_CHECK_BTN)
    html = html.replace(OLD_JS_RESET, NEW_JS_RESET)

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
print("Input redesigned. Open Anki to verify.")
