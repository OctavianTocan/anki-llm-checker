# Changelog

All notable changes to this project will be documented in this file.

## [0.2.0] - 2026-03-31

### Added

- "Open on LeetCode" link on cards with a LeetCode URL field
- Design system: shared section labels, constrained max-width, typography scale
- Modern chat-style input with circular send button (ChatGPT/Claude-inspired)
- Auto-growing textarea with `rows="1"` compact initial state
- Hidden scrollbar with gradient fade overlays when scrollable
- Patch scripts for modifying the live Anki template via SQLite/protobuf

### Changed

- Input redesigned: removed bottom bar, enter hint, and text button
- Section labels now use a shared `.section-label` class
- Card typography unified under the design system CSS

## [0.1.0] - 2026-03-30

### Added

- Initial release
- Textarea and "Check with AI" button on card front side
- Streaming LLM responses with blinking cursor animation
- Stale response guard (discards responses if user navigates away mid-stream)
- Result persistence when flipping to back side
- Configurable API key, model, base URL, and system prompt
- Light and dark theme support
- Enter to submit, Shift+Enter for newlines
- Error handling for missing API key, timeouts, and HTTP errors
