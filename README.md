# Bili Watchlater Digest

Codex skill and helper script for creating a daily digest from videos added to a Bilibili `watchlater` list.

The workflow can:

- query videos added to `watchlater` on a given date;
- download those videos with `opencli` and `yt-dlp`;
- transcribe speech with Whisper;
- translate English subtitles to Chinese with the Helsinki `opus-mt-en-zh` model;
- turn subtitles into Chinese Markdown notes;
- take helpful screenshots with `ffmpeg`;
- prepare an email summary for Gmail.

## Contents

- `skills/bili-watchlater-digest/SKILL.md`: Codex skill instructions.
- `skills/bili-watchlater-digest/scripts/run_watchlater_digest.py`: automation script.
- `skills/bili-watchlater-digest/references/workflow-notes.md`: implementation notes.

## Requirements

- Codex with local skill support.
- `opencli` with a logged-in Bilibili browser session.
- `yt-dlp` available on `PATH`.
- `ffmpeg` available on `PATH`.
- `openai-whisper` CLI available on `PATH`.
- Python packages: `torch>=2.6`, `transformers`, `sentencepiece`, `sacremoses`.
- Optional: Gmail connector access if you want Codex to create or send summary emails.

## Install The Skill

Copy the skill folder into your Codex skills directory:

```powershell
Copy-Item -Recurse -Force ".\skills\bili-watchlater-digest" "$env:USERPROFILE\.codex\skills\bili-watchlater-digest"
```

Restart Codex or reload skills if needed.

## Usage

Run the script directly:

```powershell
$env:PYTHONIOENCODING = "utf-8"
python ".\skills\bili-watchlater-digest\scripts\run_watchlater_digest.py" --date 2026-05-20 --quality 480p --out ".\runs\2026-05-20"
```

Useful options:

- `--date YYYY-MM-DD`: target date in `Asia/Shanghai`.
- `--quality 480p|720p|1080p|best`: download quality.
- `--limit N`: process only the first `N` videos.
- `--out <dir>`: output directory.

The script writes `watchlater.json`, `run_status.json`, `email_summary.md`, and one subdirectory per processed video.

## Email Summary

The script does not send email by itself. It writes `email_summary.md`; Codex can use the Gmail connector to create or send an email using that file.

## Git Hygiene

Generated videos, subtitles, screenshots, notes, and run outputs are ignored by git.
