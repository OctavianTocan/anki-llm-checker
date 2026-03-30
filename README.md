# Anki LLM Answer Checker

An Anki add-on that lets you type your understanding of a flashcard and get AI-powered feedback before flipping to the answer.

Instead of Anki's built-in exact string matching, this add-on sends your answer to an LLM that assesses conceptual understanding — whether you grasp the approach, key data structures, complexity, and edge cases. It suggests an Anki button (Again / Hard / Good / Easy) based on your response quality.

## How it works

```
Card Template (textarea + button)
        │  pycmd("llmcheck::" + answer)
        ▼
Python Add-on (reads card fields, builds prompt)
        │  HTTP SSE stream
        ▼
OpenAI-compatible API (Vercel AI Gateway)
        │  tokens streamed back
        ▼
Card Template (displays response with blinking cursor)
```

1. A textarea and "Check with AI" button are added to your card template's front side
2. Type your answer, press Enter (or click the button)
3. The add-on streams the LLM response token-by-token into the card
4. Feedback persists when you flip to the back side

## Installation

1. Clone or download this repo
2. Symlink (or copy) the `src/` folder into your Anki add-ons directory:

   ```bash
   # macOS
   ln -s /path/to/anki-llm-checker/src \
     ~/Library/Application\ Support/Anki2/addons21/llm_answer_checker

   # Linux
   ln -s /path/to/anki-llm-checker/src \
     ~/.local/share/Anki2/addons21/llm_answer_checker

   # Windows (run as admin)
   mklink /D "%APPDATA%\Anki2\addons21\llm_answer_checker" C:\path\to\anki-llm-checker\src
   ```

3. Restart Anki

## Configuration

Go to **Tools > Add-ons > LLM Answer Checker > Config** and set:

| Key | Description | Default |
|-----|-------------|---------|
| `api_key` | Your API key (required) | `""` |
| `model` | Model ID | `"zai/glm-5-turbo"` |
| `base_url` | OpenAI-compatible API base URL | `"https://ai-gateway.vercel.sh/v1"` |
| `system_prompt` | Custom system prompt (blank = default) | `""` |

Any OpenAI-compatible API works — Vercel AI Gateway, OpenRouter, local Ollama, etc.

## Card template setup

Add the contents of `card-template-front.html` to your card template's front side in Anki (via **Tools > Manage Note Types > Cards > Front Template**). The template provides the textarea, button, result display, and all styling. It works with both light and dark Anki themes.

## Security

- API key is stored in Anki's add-on config, never in card templates
- Card templates are safe to export and share
- All API calls go over HTTPS
- LLM output is rendered via `innerText` (not `innerHTML`) to prevent injection

## License

[MIT](LICENSE)
