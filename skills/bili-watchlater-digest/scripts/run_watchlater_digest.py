from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


WATCHLATER_URL = "https://www.bilibili.com/watchlater/#/list"
WATCHLATER_API = "https://api.bilibili.com/x/v2/history/toview/web"
DEFAULT_OUT_ROOT = Path.cwd() / "bili-watchlater-runs"
SESSION = "bili-watchlater-digest"
TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")
PROPER_NOUNS = {
    "Bilibili",
    "Whisper",
    "Helsinki",
    "iPod",
    "Robert Fulton",
    "Gibbons v. Ogden",
    "median voter",
    "profits",
    "entrepreneurship",
    "rent seeking",
}


@dataclass
class SrtItem:
    start: float
    end: float
    text: str


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=check,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
    )


def sanitize(value: str, limit: int = 80) -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value)
    value = re.sub(r"\s+", "_", value).strip("._ ")
    return (value[:limit] or "untitled").strip("._ ")


def fmt_mmss(seconds: float) -> str:
    total = int(round(seconds))
    return f"{total // 60:02d}:{total % 60:02d}"


def fmt_hhmmss(seconds: float) -> str:
    total = int(round(seconds))
    return f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"


def parse_time(value: str) -> float:
    h, m, rest = value.split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def parse_srt(path: Path) -> list[SrtItem]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    blocks = re.split(r"\n\s*\n", text.strip())
    items: list[SrtItem] = []
    for block in blocks:
        lines = [line.strip("\ufeff") for line in block.splitlines() if line.strip()]
        if len(lines) < 3 or "-->" not in lines[1]:
            continue
        start_s, end_s = [part.strip() for part in lines[1].split("-->")]
        items.append(SrtItem(parse_time(start_s), parse_time(end_s), " ".join(lines[2:]).strip()))
    return items


def write_srt(items: list[SrtItem], path: Path) -> None:
    parts = []
    for idx, item in enumerate(items, start=1):
        parts.append(
            f"{idx}\n{to_srt_time(item.start)} --> {to_srt_time(item.end)}\n{item.text}\n"
        )
    path.write_text("\n".join(parts), encoding="utf-8")


def to_srt_time(seconds: float) -> str:
    ms_total = int(round(seconds * 1000))
    h = ms_total // 3_600_000
    ms_total %= 3_600_000
    m = ms_total // 60_000
    ms_total %= 60_000
    s = ms_total // 1000
    ms = ms_total % 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def fetch_watchlater(day: str) -> list[dict]:
    run(["opencli.cmd", "browser", SESSION, "open", WATCHLATER_URL])
    time.sleep(2)
    js = (
        "(async()=>{const r=await fetch('"
        + WATCHLATER_API
        + "',{credentials:'include'});return JSON.stringify(await r.json())})()"
    )
    result = run(["opencli.cmd", "browser", SESSION, "eval", js])
    data = json.loads(result.stdout.strip())
    if data.get("code") != 0:
        raise RuntimeError(f"Bilibili watchlater API failed: {data}")
    videos = data.get("data", {}).get("list", [])
    filtered = []
    for video in videos:
        added = datetime.fromtimestamp(video.get("add_at", 0), TZ).strftime("%Y-%m-%d")
        if added == day:
            filtered.append(video)
    return filtered


def download_video(video: dict, target: Path, quality: str) -> Path:
    target.mkdir(parents=True, exist_ok=True)
    bvid = video["bvid"]
    run(
        [
            "opencli.cmd",
            "bilibili",
            "download",
            bvid,
            "--quality",
            quality,
            "--output",
            str(target),
            "--site-session",
            "persistent",
            "-f",
            "yaml",
        ]
    )
    candidates = [
        p
        for p in target.iterdir()
        if p.is_file() and p.suffix.lower() in {".mp4", ".mkv", ".webm", ".flv"}
    ]
    if not candidates:
        raise FileNotFoundError(f"No downloaded video found for {bvid} in {target}")
    return max(candidates, key=lambda p: p.stat().st_size)


def transcribe(video_path: Path, out_dir: Path, model: str, device: str) -> Path | None:
    run(
        [
            "whisper",
            str(video_path),
            "--task",
            "transcribe",
            "--model",
            model,
            "--device",
            device,
            "--output_format",
            "all",
            "--output_dir",
            str(out_dir),
        ]
    )
    srt_files = sorted(out_dir.glob("*.srt"), key=lambda p: p.stat().st_mtime, reverse=True)
    return srt_files[0] if srt_files else None


def effective_text(items: list[SrtItem]) -> str:
    return " ".join(item.text.strip() for item in items if item.text.strip())


def is_no_subtitle(items: list[SrtItem]) -> bool:
    text = effective_text(items)
    if len(text) < 60:
        return True
    normalized = re.sub(r"\W+", "", text.lower())
    if len(normalized) < 40:
        return True
    lines = [item.text.strip() for item in items if item.text.strip()]
    if not lines:
        return True
    most_common_count = max(lines.count(line) for line in set(lines))
    if most_common_count / len(lines) > 0.45:
        return True
    music_markers = ["music", "音乐", "字幕", "subscribe", "点赞", "打赏"]
    marker_hits = sum(text.lower().count(marker.lower()) for marker in music_markers)
    return marker_hits > 8 and len(set(lines)) < max(8, len(lines) // 5)


def mostly_english(text: str) -> bool:
    letters = len(re.findall(r"[A-Za-z]", text))
    cjk = len(re.findall(r"[\u3400-\u9fff]", text))
    return letters >= 12 and letters > cjk * 2


def load_translator():
    from transformers import MarianMTModel, MarianTokenizer

    model_name = "Helsinki-NLP/opus-mt-en-zh"
    tokenizer = MarianTokenizer.from_pretrained(model_name)
    model = MarianMTModel.from_pretrained(model_name)
    return tokenizer, model


def translate_texts(texts: list[str], cache_path: Path) -> list[str]:
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    tokenizer = model = None
    translated: list[str] = []
    for text in texts:
        if not mostly_english(text):
            translated.append(text)
            continue
        if text in cache:
            translated.append(cache[text])
            continue
        if tokenizer is None or model is None:
            tokenizer, model = load_translator()
        encoded = tokenizer([text], return_tensors="pt", padding=True, truncation=True, max_length=512)
        output = model.generate(**encoded, max_new_tokens=512)
        zh = tokenizer.batch_decode(output, skip_special_tokens=True)[0]
        cache[text] = zh
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        translated.append(zh)
    return translated


def translate_srt_if_needed(items: list[SrtItem], out_dir: Path) -> tuple[list[SrtItem], Path | None]:
    text = effective_text(items)
    if not mostly_english(text):
        return items, None
    translated_texts = translate_texts([item.text for item in items], out_dir / ".helsinki-cache.json")
    translated_items = [
        SrtItem(item.start, item.end, translated_text)
        for item, translated_text in zip(items, translated_texts, strict=True)
    ]
    path = out_dir / "translated.zh.srt"
    write_srt(translated_items, path)
    return translated_items, path


def screenshot_needed(text: str) -> bool:
    triggers = [
        "这里",
        "这儿",
        "这么",
        "网址",
        "地址",
        "公式",
        "方程",
        "图表",
        "图",
        "PPT",
        "PowerPoint",
        "代码",
        "UI",
        "界面",
        "对比",
        " versus ",
        " vs ",
    ]
    lower = text.lower()
    return any(trigger.lower() in lower for trigger in triggers)


def take_screenshot(video_path: Path, seconds: float, shot_dir: Path) -> str:
    shot_dir.mkdir(parents=True, exist_ok=True)
    name = f"shot-{fmt_mmss(seconds).replace(':', '-')}.jpg"
    path = shot_dir / name
    run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            fmt_hhmmss(seconds),
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(path),
        ]
    )
    return f"![Screenshot {fmt_mmss(seconds)}]({path.as_posix()})"


def punctuate(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace(" ,", "，").replace(" .", "。").replace(" ?", "？").replace(" !", "！")
    if text and text[-1] not in "。！？.!?）)]":
        text += "。"
    return text


def build_notes(items: list[SrtItem], video_path: Path, out_dir: Path) -> Path:
    shot_dir = out_dir / "screenshots"
    lines: list[str] = []
    chunk_seconds = 300
    chunks: list[list[SrtItem]] = []
    current: list[SrtItem] = []
    current_start = items[0].start if items else 0
    for item in items:
        if current and item.start - current_start >= chunk_seconds:
            chunks.append(current)
            current = []
            current_start = item.start
        current.append(item)
    if current:
        chunks.append(current)

    for idx, chunk in enumerate(chunks):
        if idx == 1:
            lines.append("## 第一段")
            lines.append("")
        elif idx > 1:
            lines.append(f"## 第{idx}段")
            lines.append("")
        paragraph_parts: list[str] = []
        last_shot_at = -9999.0
        for item in chunk:
            sentence = punctuate(item.text)
            if screenshot_needed(sentence) and item.end - last_shot_at > 90:
                sentence += " " + take_screenshot(video_path, item.end, shot_dir)
                last_shot_at = item.end
            paragraph_parts.append(sentence)
        lines.append(" ".join(paragraph_parts))
        lines.append("")

    path = out_dir / "notes.md"
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return path


def build_email_summary(day: str, results: list[dict], run_dir: Path) -> Path:
    lines = [f"# Bilibili 稍后再看日报 - {day}", ""]
    lines.append(f"共处理 {len(results)} 个视频。")
    lines.append("")
    for item in results:
        lines.append(f"## {item.get('title', item.get('bvid', '未知视频'))}")
        lines.append("")
        lines.append(f"- BV：{item.get('bvid', '')}")
        lines.append(f"- UP：{item.get('author', '')}")
        lines.append(f"- 状态：{item.get('status', '')}")
        if item.get("note"):
            lines.append(f"- 笔记：{item['note']}")
        if item.get("subtitle"):
            lines.append(f"- 字幕：{item['subtitle']}")
        if item.get("error"):
            lines.append(f"- 错误：{item['error']}")
        if item.get("status") == "no_subtitle":
            lines.append("- 摘要：无字幕或无有效语音，未生成笔记。")
        lines.append("")
    path = run_dir / "email_summary.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def process_video(video: dict, run_dir: Path, quality: str, whisper_model: str, device: str) -> dict:
    bvid = video["bvid"]
    title = video.get("title", bvid)
    author = video.get("owner", {}).get("name", "")
    video_dir = run_dir / f"{bvid}_{sanitize(title)}"
    result = {"bvid": bvid, "title": title, "author": author, "status": "started"}
    try:
        downloaded = download_video(video, video_dir, quality)
        result["downloaded"] = str(downloaded)
        srt = transcribe(downloaded, video_dir, whisper_model, device)
        if not srt:
            result["status"] = "no_subtitle"
            return result
        items = parse_srt(srt)
        if is_no_subtitle(items):
            result["status"] = "no_subtitle"
            result["subtitle"] = str(srt)
            return result
        note_items, translated_srt = translate_srt_if_needed(items, video_dir)
        notes = build_notes(note_items, downloaded, video_dir)
        result["status"] = "notes_created"
        result["subtitle"] = str(translated_srt or srt)
        result["note"] = str(notes)
        return result
    except Exception as exc:
        result["status"] = "failed"
        result["error"] = str(exc)
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a Bilibili watchlater daily digest.")
    parser.add_argument("--date", default=datetime.now(TZ).strftime("%Y-%m-%d"))
    parser.add_argument("--out", default=None)
    parser.add_argument("--quality", default="480p", choices=["480p", "720p", "1080p", "best"])
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--whisper-model", default="medium")
    parser.add_argument("--device", default="cuda")
    args = parser.parse_args()

    run_dir = Path(args.out) if args.out else DEFAULT_OUT_ROOT / args.date
    run_dir.mkdir(parents=True, exist_ok=True)
    videos = fetch_watchlater(args.date)
    if args.limit is not None:
        videos = videos[: args.limit]
    (run_dir / "watchlater.json").write_text(json.dumps(videos, ensure_ascii=False, indent=2), encoding="utf-8")

    results: list[dict] = []
    for video in videos:
        results.append(process_video(video, run_dir, args.quality, args.whisper_model, args.device))
        (run_dir / "run_status.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = build_email_summary(args.date, results, run_dir)
    print(json.dumps({"date": args.date, "run_dir": str(run_dir), "videos": len(videos), "summary": str(summary)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
