# Phase L — Localization (planned, not started)

Only on user request. RTCW on Steam is English-only: `text/EnglishUSA/` (briefings, objectives), `text/strings.txt` and
`text/pickupnames.txt` are English, the menus hardcode English text (so do the codmod additions), and `cl_language`
only changes key names (`iortcw/SP/code/client/cl_keys.c`). Retail localized editions shipped their own text and audio;
community packs extracted from them exist (links in the root [README](../README.md#localization-community-patches)).

| Phase | Deliverable |
|---|---|
| L0 | Translate the menus and the game data that exists: mission briefings and objectives (`text/<Lang>/`), `strings.txt`, `pickupnames.txt`, and the codmod menu deltas and HUD strings. Menus hardcode text, so this needs a string layer or one overlay pk3 per language. The community packs show what the retail localized data looks like. |
| L1 | There are no subtitles to reuse, so make them: transcribe all dialogue audio with AI speech-to-text, then add a subtitle display in cgame. |
| L2 | Translate the L1 subtitles with AI. |

Policy: generated packs are derived from game assets, so they stay local and private, like the HD packs. Exception (owner's decision, 2026-10-15): the final subtitle text (`tools/subtitles/build/text/subtitles.txt`, and `cache.json` with the manual fixes) is committed; the pk3 and review/sample audio are not. Tools go in
`tools/`, outputs are not committed.

## Policy: translations are committed (2026-10-16)

`mod/codmod/lang/<code>/` (strings, subtitles, briefing texts, flags) is committed so anyone can re-pack it with
`tools/l10n/pack.py`; the generated `codmod_lang_*.pk3` files stay in `run/` and are not committed. English subtitle text
still comes from the private `codmod_subtitles.pk3`. Implementation and format: `docs/languages.md`.
