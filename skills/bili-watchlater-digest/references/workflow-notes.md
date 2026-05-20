# Workflow Notes

## Bilibili Watchlater Source

Use the logged-in browser session and fetch:

`https://api.bilibili.com/x/v2/history/toview/web`

Filter `data.list` by `add_at` using `Asia/Shanghai` calendar date. Useful fields include:

- `title`
- `bvid`
- `owner.name`
- `uri`
- `add_at`
- `duration`
- `viewed`

## English Translation

For English subtitles, use `Helsinki-NLP/opus-mt-en-zh` through `transformers`:

- `MarianTokenizer.from_pretrained("Helsinki-NLP/opus-mt-en-zh")`
- `MarianMTModel.from_pretrained("Helsinki-NLP/opus-mt-en-zh")`

Keep proper nouns in English when translation makes them worse. The generated notes may be polished by Codex after script output, but should not remove content.

## Gmail Draft

After the script creates `email_summary.md`, call Gmail `_create_draft` with:

- `to`: the user's Gmail address, or the address explicitly requested by the user
- `subject`: `Bilibili 稍后再看日报 - <YYYY-MM-DD>`
- `body`: Markdown summary text

Never send the draft unless the user explicitly asks.
