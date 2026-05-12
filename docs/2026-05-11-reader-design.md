# Lector Reader Mode — Design (v1.0)

**Date:** 2026-05-11
**Status:** Approved
**Scope:** Tonight's MVP for the Reader half of the locked v1 scope (Markdown Reader + Editor + Read Along default + Read Along custom).

## Decisions

- **Surface model:** Edit and Read are two modes of the same single pane, toggled via segmented control. Not split-pane, not Typora-style WYSIWYG.
- **Highlight granularity in Reader:** paragraph-level only for v1.0 MVP. Word-level inside Reader is deferred.
- **Visual register:** adopts the lector-web magazine register established in the 5/9 redesign — Newsreader serif body, Plus Jakarta Sans UI, ink-slate light / parchment-gold dark.

## Design tokens

| Token | Light | Dark |
|---|---|---|
| `--bg` | `#FFFFFF` | `#09090B` |
| `--text` | `#0F0F0F` | `#F4F4F5` |
| `--accent` | `#1F2937` (ink-slate) | `#C9B976` (parchment gold) |
| `--accent-h` | `#0F172A` | `#B5A560` |
| `--muted` | `#6B7280` | `#A1A1AA` |
| `--surface` | `#F7F7F8` | `#111113` |
| `--border` | `#E4E4E7` | `#27272A` |
| `--mark` | accent at 12% alpha | accent at 18% alpha |
| `--font` | `'Plus Jakarta Sans', system-ui, sans-serif` | same |
| `--font-display` | `'Newsreader', Georgia, serif` | same |

Existing `--danger` (`#dc2626`) carries over unchanged.

Optional: 5% fractal-noise SVG body background, identical to lector-web.

## Toggle UX

- Segmented control top-left of toolbar, immediately right of the brand: `[Edit] [Read]`.
- Active segment: `--accent` fill, white text. Inactive: transparent, `--text` color, hover surface.
- Keyboard: `Ctrl/Cmd+E` toggles. Browser-reserved `Ctrl+R` left alone.
- State persists across the session as `body.mode-edit` / `body.mode-read` class. Initial state on app load: Edit.
- Toggling preserves the current sentence index so playback resume is consistent across modes.

## Reader rendering

- Markdown library: `marked.min.js` vendored to `static/vendor/` (offline-first, ~50KB).
- New DOM: `<article id="reader" class="prose">` lives alongside `#editor-wrap` inside the editor slot. CSS class on body shows one and hides the other (no DOM teardown).
- Render trigger: `marked.parse(editor.value)` runs (a) on first toggle to Read, (b) on subsequent toggles if `editor.value` changed.
- Sentence wrapping (post-render DOM walk): iterate text nodes inside `p, li, blockquote, h1-h6`, split each text run on sentence-ending punctuation using the existing `splitSentences` regex, and wrap each chunk in `<span class="lector-sentence" data-idx="N">`. `N` is the same index `parseUnits` produces, so playback dispatch and Reader highlight target are unified.
- Sentence wrapping skips text nodes inside `<code>`, `<pre>`, and `<a>` to avoid breaking inline tokens.

## Read Along — Reader mode

- `startHighlights` gains a mode branch.
- In Read mode: look up `span.lector-sentence[data-idx="${i}"]`, remove `.lector-active` from any previous span, add to the new one. `scrollIntoView({block: 'center', behavior: 'smooth'})`. Word-level updates from `data.words` are ignored in Read mode for v1.0.
- In Edit mode: unchanged.
- `.lector-active` style: background `--mark`, subtle padding (`0 2px`), 2px border radius.

## Reader typography (prose styles)

| Element | Style |
|---|---|
| Container | `max-width: 720px; margin: 0 auto; padding: 48px 24px;` |
| Body | `font: 18px/1.7 var(--font-display); color: var(--text);` |
| `h1` | `2.25em; font-weight: 700; margin: 1.6em 0 0.3em; border-bottom: 1px solid var(--border); padding-bottom: 0.3em;` |
| `h2` | `1.6em; font-weight: 700; margin: 1.4em 0 0.3em;` |
| `h3` | `1.25em; font-weight: 600; margin: 1.2em 0 0.3em;` |
| `p` | `margin: 0 0 1em;` |
| `blockquote` | `border-left: 3px solid var(--accent); padding: 0.2em 1em; color: var(--muted); font-style: italic; margin: 1em 0;` |
| `code` (inline) | `font: 0.88em/1 ui-monospace, 'Cascadia Code', monospace; background: var(--surface); padding: 0.15em 0.35em; border-radius: 3px;` |
| `pre` | `background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 1em; overflow-x: auto;` |
| `pre code` | `background: transparent; padding: 0;` |
| `a` | `color: var(--accent); text-decoration: none; border-bottom: 1px solid transparent;` hover adds bottom border |
| `hr` | `border: none; border-top: 1px solid var(--border); margin: 2em 0;` |
| `ul, ol` | `padding-left: 1.5em; margin: 0 0 1em;` |
| `li` | `margin: 0.3em 0;` |
| `img` | `max-width: 100%; height: auto; border-radius: 4px;` |
| `table` | `border-collapse: collapse; width: 100%; margin: 1em 0;` |
| `th, td` | `border: 1px solid var(--border); padding: 0.4em 0.7em; text-align: left;` |
| `th` | `background: var(--surface); font-weight: 600;` |

## Editor mode (light cleanup, not a rewrite)

- Keep `<textarea>`.
- Restyle to magazine register: Newsreader 18px body, 720px max-width matching Reader, ink-slate / parchment-gold caret + selection.
- Remove all `#7C3AED` violet references; map every existing token to the new palette.

## Out of scope (deferred to Tue UX block or later)

- Editor syntax highlighting / inline markdown rendering
- Word-level highlighting inside Reader mode (paragraph-only for now)
- Table of contents sidebar
- Reader font-size / line-height user controls
- Print stylesheet
- Live render while typing in Edit mode (re-render only on toggle for now)

## Acceptance criteria

1. Opening Lector lands on Edit mode with the new magazine register applied.
2. Clicking `[Read]` (or `Ctrl/Cmd+E`) swaps to a rendered Markdown view of the same `editor.value`.
3. Headings, lists, blockquotes, code, tables, and links all render with Newsreader serif typography and the new palette.
4. Pressing Play in Read mode highlights the active sentence as `.lector-active` and auto-scrolls to keep it centered.
5. Pressing Play in Edit mode preserves existing word-level (Kokoro) or sentence-level (custom voice) textarea highlighting.
6. Switching back to Edit mode after Reader playback resumes from the same sentence index.
7. Dark-mode toggle (existing `🌙` button) applies the parchment-gold palette to both modes.

## Implementation notes

- `marked` is bundled offline; do not load from CDN.
- Sentence wrapping must skip text nodes inside `<code>`, `<pre>`, and `<a>` (no false-positive splits).
- The post-render DOM walk runs once per render, not per playback frame.
- All visual changes confined to `static/index.html`, `static/style.css`, `static/vendor/marked.min.js`. No Python changes.
