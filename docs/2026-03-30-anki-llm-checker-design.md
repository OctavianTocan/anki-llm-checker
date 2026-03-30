# Anki LLM Answer Checker — Design Spec

**Date:** 2026-03-30
**Status:** Draft

## Problem

During Anki review of LeetCode flashcards, there's no way to test
understanding by typing an answer and getting intelligent feedback before
flipping the card. Anki's built-in "type in the answer" only does exact
string matching, which is useless for assessing conceptual understanding of
algorithm solutions.

## Solution

A two-part system:

1. **Card template additions** — a textarea, "Check" button, and result
   display area added to the LeetCode Problem card template's front side
2. **Minimal Python add-on** — an API proxy that holds the Vercel Gateway
   key and relays requests to `zai/glm-5-turbo`

The card template owns all UI. The add-on owns all secrets and network calls.

## Architecture

```
┌─────────────────────────────────────────────┐
│  Card Template (Front Side)                 │
│                                             │
│  {{Front}}  (the problem statement)         │
│                                             │
│  ┌───────────────────────────────────────┐  │
│  │  <textarea> Your answer here...       │  │
│  └───────────────────────────────────────┘  │
│  [ Check with AI ]                          │
│                                             │
│  ┌───────────────────────────────────────┐  │
│  │  #llm-result (hidden until response)  │  │
│  │  "Good understanding of the BFS       │  │
│  │   approach, but you missed the edge   │  │
│  │   case where... → suggest: Good"      │  │
│  └───────────────────────────────────────┘  │
└──────────────────┬──────────────────────────┘
                   │ pycmd("llmcheck::" + JSON.stringify(answer))
                   ▼
┌─────────────────────────────────────────────┐
│  Python Add-on (~60 lines)                  │
│                                             │
│  webview_did_receive_js_message handler     │
│  ├─ Reads current card's note fields        │
│  ├─ Stores current card ID for staleness    │
│  ├─ Builds prompt with all fields + answer  │
│  ├─ POST to Vercel Gateway (background      │
│  │  thread via urllib, 15s timeout)         │
│  ├─ On success: caches result, pushes to    │
│  │  webview via mw.taskman.run_on_main()   │
│  └─ On error: pushes error message          │
│                                             │
│  reviewer_did_show_answer hook              │
│  └─ Re-injects cached result into back side │
│                                             │
│  config.json:                               │
│    api_key: <vercel gateway key>            │
│    model: zai/glm-5-turbo                   │
└─────────────────────────────────────────────┘
```

## Card Template (Front Side)

Added below the existing `{{Front}}` content:

```html
<div id="llm-checker">
  <textarea id="llm-input" placeholder="Type your answer..."
    onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();checkAnswer();}">
  </textarea>
  <button onclick="checkAnswer()">Check with AI</button>
  <div id="llm-result" style="display:none;"></div>
</div>

<script>
function checkAnswer() {
  var answer = document.getElementById('llm-input').value;
  if (!answer.trim()) return;
  document.getElementById('llm-result').style.display = 'block';
  document.getElementById('llm-result').innerText = 'Checking...';
  pycmd('llmcheck::' + JSON.stringify(answer));
}

function showLLMResult(text) {
  var el = document.getElementById('llm-result');
  if (!el) return;
  el.style.display = 'block';
  el.innerText = text;
}

function showLLMError(text) {
  var el = document.getElementById('llm-result');
  if (!el) return;
  el.style.display = 'block';
  el.innerText = '⚠ ' + text;
}
</script>
```

Styling should be minimal and match Anki's default dark/light themes. The
textarea and result area should be full-width within the card.

Enter triggers check (Shift+Enter for newlines). Button also works.

## Python Add-on

### File structure

```
addons21/llm_answer_checker/
├── __init__.py    # ~60 lines: hooks + API call
├── config.json    # default config
└── manifest.json  # add-on metadata
```

### config.json

```json
{
  "api_key": "",
  "model": "zai/glm-5-turbo",
  "base_url": "https://ai-gateway.vercel.sh/v1"
}
```

### __init__.py behavior

**State:** The add-on holds two module-level variables:
- `_current_card_id`: the card ID when the check was initiated
- `_last_result`: the most recent LLM response text (for re-injection)

**Hook 1 — `webview_did_receive_js_message`:**

1. When a message starting with `llmcheck::` arrives:
   a. Parse the user's answer via `json.loads()` (undoes the
      `JSON.stringify` escaping from JS)
   b. Get the current card via `mw.reviewer.card`; store its `id` in
      `_current_card_id`
   c. Read all fields from the card's note
   d. Build the system + user prompt (see below)
   e. Spawn a `threading.Thread` to POST to `{base_url}/chat/completions`
      with a 15-second timeout
   f. On success: if `mw.reviewer.card.id == _current_card_id` (not
      stale), cache the result in `_last_result` and call
      `mw.reviewer.web.eval("showLLMResult(...)")` on the main thread
      via `mw.taskman.run_on_main()`
   g. On error (timeout, HTTP error, bad JSON): push
      `showLLMError("message")` instead

**Hook 2 — `reviewer_did_show_answer`:**

1. If `_last_result` is set and `_current_card_id` matches the current
   card, re-inject the result into the back side via
   `mw.reviewer.web.eval("showLLMResult(...)")`

**Hook 3 — `reviewer_did_show_question`:**

1. Clear `_last_result` and `_current_card_id` when a new card appears,
   so stale results from previous cards are never shown.

### LLM Prompt

**System:**
```
You are a flashcard review assistant. The user is studying algorithm
problems and testing their understanding. You will receive the flashcard's
fields and the user's typed answer.

Assess how well the user understands the concept — not whether they wrote
exact code, but whether they grasp the approach, key data structures,
time/space complexity, and edge cases.

Respond with:
1. A brief assessment of their understanding (2-3 sentences)
2. Any gaps or misconceptions you notice
3. A suggested Anki button: Again / Hard / Good / Easy

Keep it concise. Use plain text, no markdown.
```

**User message:**
```
Card fields:
- Front: {front}
- Implementation: {implementation}
- Gotchas: {gotchas}
- LeetCode URL: {url}

My answer:
{user_typed_answer}
```

## Security

- API key lives only in the add-on's `config.json` inside the Anki
  profile directory — never in card templates
- Card template is safe to export/share
- API calls go over HTTPS to Vercel Gateway
- LLM output rendered via `innerText` (not `innerHTML`) to prevent
  any injection from model output

## Error Handling

- **Empty API key:** show "Set your API key in Tools → Add-ons →
  llm_answer_checker → Config"
- **Network timeout (15s):** show "Request timed out — check your
  connection"
- **HTTP error (4xx/5xx):** show "API error: {status code}"
- **Malformed response:** show "Unexpected response from API"

## Limitations

- Only works on the LeetCode Problem note type (by design — this is the
  only template that will have the HTML)
- Requires Anki to be online for the API call
- API latency (~1-3s) means the result isn't instant

## Resolved Decisions

1. **Feedback persists after flip** — the back template uses
   `{{FrontSide}}`, which re-renders the front HTML (without JS state).
   The add-on's `reviewer_did_show_answer` hook re-injects the cached
   LLM result into the back side so feedback is visible after flipping.
2. **Trigger: button + Enter key** — pressing Enter while focused in the
   textarea triggers the check. Shift+Enter inserts a newline.
3. **Stale response guard** — the add-on tracks card ID and discards
   API responses that arrive after the user has moved to a different card.
4. **JS→Python escaping** — user answer is `JSON.stringify()`'d before
   passing through `pycmd()`, then `json.loads()`'d in Python. This
   handles quotes, newlines, and special characters safely.
