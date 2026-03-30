"""LLM Answer Checker — Anki add-on for AI-powered flashcard review.

Adds an interactive text input to the card reviewer where the user types
their understanding of the problem. The add-on streams the response from
an OpenAI-compatible API (via Vercel AI Gateway) and displays it
token-by-token in the webview with a blinking cursor.

Architecture:
    Card Template (HTML/JS)  ──pycmd──>  Python Add-on  ──HTTP SSE──>  API
         streamLLMChunk()    <──eval───  background thread  <──chunks──
         finalizeLLMStream() <──eval───  main thread        <──[DONE]──

The card template owns all UI (textarea, button, result display).
This module owns secrets (API key in config.json) and network calls.

Config (Tools → Add-ons → llm_answer_checker → Config):
    api_key:       Vercel AI Gateway API key
    model:         Model ID (e.g. "zai/glm-5-turbo", "google/gemini-3.1-pro-preview")
    base_url:      OpenAI-compatible base URL
    system_prompt: Custom system prompt (leave blank for default)
"""

import json
import re
import threading
import urllib.request
import urllib.error

from aqt import mw, gui_hooks

# Module-level state tracking the current review session.
# _current_card_id prevents stale API responses from injecting into a
# different card if the user navigates away mid-stream.
_current_card_id: int | None = None
# _last_result caches the final response so the reviewer_did_show_answer
# hook can re-inject it when the user flips to the back side.
_last_result: str | None = None


def _get_config() -> dict:
    """Read the add-on configuration from Anki's config system.

    @returns Merged config dict (config.json defaults + user's meta.json overrides).
    """
    return mw.addonManager.getConfig(__name__)


def _push_js(js_call: str) -> None:
    """Schedule a JavaScript eval on the reviewer webview's main thread.

    @param js_call  JavaScript expression to evaluate.

    Uses mw.taskman.run_on_main because the streaming thread cannot
    touch Qt widgets directly — all webview interaction must happen
    on the main thread.
    """
    def _run():
        if mw.reviewer and mw.reviewer.web:
            mw.reviewer.web.eval(js_call)
    mw.taskman.run_on_main(_run)


def _is_stale(card_id: int) -> bool:
    """Check if the user has navigated away from the card that initiated the request.

    @param card_id  The card ID captured when the check was initiated.
    @returns True if the current reviewer card differs from card_id.
    """
    return not (mw.reviewer and mw.reviewer.card
                and mw.reviewer.card.id == card_id)


def _call_api(user_answer: str, fields: dict[str, str], card_id: int) -> None:
    """POST to the API with streaming enabled and push chunks to the webview.

    Runs in a daemon thread spawned by _on_js_message. Reads the SSE stream
    line-by-line, accumulates the full response, and pushes each intermediate
    state to streamLLMChunk() in the webview. On completion, calls
    finalizeLLMStream() on the main thread for verdict extraction.

    @param user_answer  The text the user typed in the card template textarea.
    @param fields       Dict mapping field names to their HTML content.
    @param card_id      Card ID for staleness checks during streaming.
    """
    global _last_result

    config = _get_config()
    api_key = config.get("api_key", "")
    if not api_key:
        _push_js(
            'showLLMError("Set your API key in Tools → Add-ons '
            '→ llm_answer_checker → Config")'
        )
        return

    model = config.get("model", "zai/glm-5-turbo")
    base_url = config.get("base_url", "https://ai-gateway.vercel.sh/v1")

    default_prompt = (
        "You are a flashcard review assistant. The user is studying algorithm "
        "problems and testing their understanding. You will receive the "
        "flashcard's fields and the user's typed answer.\n\n"
        "Assess how well the user understands the concept — not whether they "
        "wrote exact code, but whether they grasp the approach, key data "
        "structures, time/space complexity, and edge cases.\n\n"
        "Respond with:\n"
        "1. A brief assessment of their understanding (2-3 sentences)\n"
        "2. Any gaps or misconceptions you notice\n"
        "3. A suggested Anki button: Again / Hard / Good / Easy\n\n"
        "Keep it concise. Use plain text, no markdown."
    )
    system_prompt = config.get("system_prompt", "") or default_prompt

    # Strip HTML tags from field values so the LLM sees clean text
    field_lines = []
    for name, value in fields.items():
        clean = re.sub(r"<[^>]+>", "", value).strip()
        if clean:
            field_lines.append(f"- {name}: {clean}")

    user_msg = (
        "Card fields:\n"
        + "\n".join(field_lines)
        + f"\n\nMy answer:\n{user_answer}"
    )

    payload = json.dumps({
        "model": model,
        "stream": True,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    # Open the streaming connection
    try:
        resp = urllib.request.urlopen(req, timeout=30)
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:200]
        except Exception:
            pass
        msg = f"API error {e.code}: {body}" if body else f"API error: {e.code}"
        _push_js(f"showLLMError({json.dumps(msg)})")
        return
    except (urllib.error.URLError, TimeoutError):
        _push_js('showLLMError("Request timed out — check your connection")')
        return

    # Read SSE stream line by line, pushing accumulated text on each delta
    full_text = ""
    try:
        for raw_line in resp:
            # Abort early if the user moved to a different card
            if _is_stale(card_id):
                resp.close()
                return

            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line.startswith("data: "):
                continue
            data_str = line[6:]
            if data_str == "[DONE]":
                break

            try:
                chunk = json.loads(data_str)
                delta = chunk["choices"][0]["delta"].get("content", "")
            except (json.JSONDecodeError, KeyError, IndexError):
                continue

            if delta:
                full_text += delta
                escaped = json.dumps(full_text)
                _push_js(f"streamLLMChunk({escaped})")

        resp.close()
    except Exception:
        resp.close()
        if not full_text:
            _push_js('showLLMError("Stream interrupted")')
            return

    if _is_stale(card_id):
        return

    # Cache result for re-injection on card flip, then finalize in the webview
    _last_result = full_text

    def _finalize():
        if not _is_stale(card_id):
            mw.reviewer.web.eval(f"finalizeLLMStream({json.dumps(full_text)})")

    mw.taskman.run_on_main(_finalize)


def _on_js_message(
    handled: tuple[bool, object],
    message: str,
    context: object,
) -> tuple[bool, object]:
    """Handle pycmd('llmcheck::...') messages from the card template JavaScript.

    Registered on gui_hooks.webview_did_receive_js_message. When the user
    clicks "Check" or presses Enter, the template calls
    pycmd('llmcheck::' + JSON.stringify(answer)), which arrives here.

    @param handled  Tuple (was_handled, return_value) from previous hook handlers.
    @param message  The raw string sent via pycmd().
    @param context  The webview context (reviewer, editor, etc.).
    @returns (True, None) if we handled the message, otherwise the original handled tuple.
    """
    global _current_card_id

    if not isinstance(message, str) or not message.startswith("llmcheck::"):
        return handled

    raw = message[len("llmcheck::"):]
    try:
        user_answer = json.loads(raw)
    except json.JSONDecodeError:
        user_answer = raw

    if not mw.reviewer or not mw.reviewer.card:
        return (True, None)

    card = mw.reviewer.card
    _current_card_id = card.id
    note = card.note()
    fields = {name: note[name] for name in note.keys()}

    thread = threading.Thread(
        target=_call_api,
        args=(user_answer, fields, card.id),
        daemon=True,
    )
    thread.start()

    return (True, None)


def _on_show_answer(card) -> None:
    """Re-inject the cached LLM result when the user flips to the back side.

    Because {{FrontSide}} re-renders the template HTML (losing JS state),
    this hook pushes the stored result back into the webview so the feedback
    remains visible after flipping.

    @param card  The current Anki card object.
    """
    if _last_result and _current_card_id == card.id:
        mw.reviewer.web.eval(f"showLLMResult({json.dumps(_last_result)})")


def _on_show_question(card) -> None:
    """Clear state when a new card appears in the reviewer.

    Prevents stale results from a previous card being shown on the next one.

    @param card  The new Anki card object.
    """
    global _current_card_id, _last_result
    _current_card_id = None
    _last_result = None


# --- Hook registration ---
gui_hooks.webview_did_receive_js_message.append(_on_js_message)
gui_hooks.reviewer_did_show_answer.append(_on_show_answer)
gui_hooks.reviewer_did_show_question.append(_on_show_question)
