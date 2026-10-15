# Subtitles

Voice-line subtitles for the single-player campaign (phase L1 of [phase-l10n.md](phase-l10n.md)). The text is
generated locally from the game's own audio, so the pack is derived from game assets and stays private
(`run/codmod/codmod_subtitles.pk3`, git-ignored). The final text (`tools/subtitles/build/text/subtitles.txt`) and `build/cache.json` (with the manual fixes) are committed, so `pack.py` alone rebuilds the pack from a clone.

## How it works

- `tools/subtitles/transcribe.py` extracts the voice wavs (`sound/scenaric/**` and the AI voice folders
  `sound/player/{infantryss,heinrich,eliteguard,loper,warrior,supersoldier}`) from the Steam paks, transcribes them
  with faster-whisper `large-v3` (CUDA), translates non-English lines to English with Whisper's `translate` task, and
  writes `build/text/subtitles.txt` plus `build/review.txt` (clips that need a manual look). Resumable via
  `build/cache.json`. Non-speech clips (hallucinated "thank you for watching") are dropped by VAD plus
  no-speech/log-prob thresholds.
- `tools/subtitles/pack.py` zips it to `run/codmod/codmod_subtitles.pk3`.
- `iortcw/SP/code/cgame/cg_subtitles.c` loads `text/subtitles.txt` at `CG_Init` (lines: `path seconds "text"`, sorted by
  lowercase path) and is called from the sound events (`EV_GENERAL_SOUND`, `EV_GLOBAL_SOUND`, sound scripts in
  `cg_sound.c`). `CG_DrawSubtitles` runs in `CG_Draw2D`; the rend2 present path is untouched. Voices farther than
  1200 units are skipped, except during camera cutscenes.
- Setting: `cod_subtitles` (archived, default 1), row "Subtitles" in Settings > Game and the pause menu's Game page;
  reset value in `codmod_binds.cfg`. Without the pack nothing is drawn.

## Usage

```bash
cd tools/subtitles
uv sync
uv run python transcribe.py      # ~30 min, resumable
uv run python review_server.py   # fix lines in the browser: http://127.0.0.1:8765, then "Rebuild + pack"
uv run python pack.py            # pack build/text/subtitles.txt (hand-editable: `path seconds "text"`)
uv run python pack.py --from-cache  # regenerate subtitles.txt from build/cache.json first
```

Fixing a wrong line: use `review_server.py` (audio plus an editable field per line, saved to `build/cache.json`; edits are marked `manual` and survive reruns of `transcribe.py`). Filters: needs review, missing text (add text for dropped clips), edited, all. Empty text removes a subtitle.
