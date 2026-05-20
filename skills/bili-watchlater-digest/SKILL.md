---
name: bili-watchlater-digest
description: Build a daily Bilibili watchlater digest from the user's logged-in account. Use when Codex needs to list videos added to Bilibili watchlater on a date, download them with opencli/yt-dlp, transcribe with Whisper, translate English subtitles with Helsinki, create Chinese Markdown notes with screenshots, and prepare a Gmail draft summary.
---

# Bili Watchlater Digest

## Workflow

Use this skill for Bilibili "稍后再看" daily processing. Default the date to today in `Asia/Shanghai` unless the user specifies another date.

1. Run the bundled script:

```powershell
$env:PYTHONIOENCODING="utf-8"
python "<path-to-this-skill>\scripts\run_watchlater_digest.py" --date YYYY-MM-DD
```

Optional flags:

- `--out <dir>`: override the run directory.
- `--quality 480p|720p|1080p|best`: pass through to `opencli bilibili download`; default `480p`.
- `--limit N`: process only the first N videos, useful for tests.

2. Read the generated `email_summary.md`.
3. Use the Gmail connector to create a draft, not to send:
   - `to`: the user's Gmail address, or the address explicitly requested by the user
   - `subject`: `Bilibili 稍后再看日报 - <YYYY-MM-DD>`
   - `body`: contents of `email_summary.md`

## Script Contract

The script writes to:

`<current-working-directory>\bili-watchlater-runs\<YYYY-MM-DD>` unless `--out` is provided.

For each video it creates a folder containing the downloaded video, Whisper outputs, optional `translated.zh.srt`, `notes.md`, and `screenshots/`. The run root contains:

- `watchlater.json`: raw filtered watchlater metadata.
- `run_status.json`: per-video status.
- `email_summary.md`: body text for the Gmail draft.

Statuses:

- `notes_created`: video downloaded, usable subtitles found, notes and screenshots created.
- `no_subtitle`: video downloaded but speech/subtitle text is empty, too short, or mostly repeated music/noise hallucination.
- `failed`: an exception occurred; include the error in the summary.

## Note Rules

The generated note must be Markdown body text only:

- Use Chinese as the main language.
- Preserve necessary English proper nouns, for example `Bilibili`, `Whisper`, `Helsinki`, `profits`, `entrepreneurship`, `rent seeking`, `iPod`, `Robert Fulton`, `Gibbons v. Ogden`, `median voter`.
- Do not wrap the whole note in a code block.
- Use only one heading level: `##`.
- Make the first paragraph an introduction with no heading.
- Add punctuation and paragraph formatting, but do not deliberately delete subtitle text, including repeated or imperfect Whisper text.
- Insert screenshots only when useful: code explanation, UI interaction, address/URL mentions, "这么/这里/这儿" visual references, key technical concept comparisons, charts, slides, formulas, or other visual material that helps comprehension.
- Replace every `Screenshot-[mm:ss]` marker with a local Markdown image link after taking the frame with `ffmpeg`.

## Dependencies

Expect these local tools to be available:

- `opencli.cmd` with Bilibili persistent login.
- `yt-dlp` on PATH.
- `whisper` and `ffmpeg` on PATH.
- Python packages: `torch>=2.6`, `transformers`, `sentencepiece`, `sacremoses`.
- Gmail connector access for draft creation.

If Bilibili or Gmail login is missing, stop and ask the user to reconnect or log in. Do not silently send mail; create a draft only unless the user explicitly requests sending.
