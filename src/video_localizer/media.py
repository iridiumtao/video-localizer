from __future__ import annotations

import json
import math
import subprocess
import wave
from dataclasses import dataclass, asdict
from pathlib import Path
from urllib.parse import urlparse


@dataclass
class Segment:
    start: float
    end: float
    text: str


def run(args: list[str]) -> str:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"{args[0]} failed: {result.stderr[-3000:]}")
    return result.stdout


def ffmpeg(*args: str) -> None:
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", *args])


def duration(path: Path) -> float:
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)]))


def acquire(source: str, work: Path, cookies: Path | None = None) -> Path:
    url = urlparse(source)
    if url.scheme:
        if url.scheme != "https" or url.hostname not in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"} or url.username or url.password or url.port not in (None, 443):
            raise ValueError("請提供 HTTPS YouTube 連結或本機影片路徑")
        import yt_dlp
        options = {"format": "bv*[height<=1080]+ba/b[height<=1080]", "merge_output_format": "mp4", "outtmpl": str(work / "source.%(ext)s"), "noplaylist": True, "socket_timeout": 30, "retries": 2,
                   "match_filter": lambda info, **kwargs: "不支援直播" if info.get("is_live") else None}
        if cookies:
            options["cookiefile"] = str(cookies)
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(source, download=True)
            if info.get("is_live"):
                raise ValueError("不支援直播")
            path = Path(downloader.prepare_filename(info))
            merged = path.with_suffix(".mp4")
            return merged if merged.exists() else path
    path = Path(source).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"找不到影片：{path}")
    return path


def normalize(segments: list[Segment], total: float) -> list[Segment]:
    result = []
    cursor = 0.0
    for seg in sorted(segments, key=lambda s: s.start):
        if not math.isfinite(seg.start) or not math.isfinite(seg.end):
            raise ValueError("Invalid segment timestamps")
        start, end = max(0, cursor, seg.start), min(total, seg.end)
        text = " ".join(seg.text.split()).strip()
        if end - start >= .001 and text:
            result.append(Segment(start, end, text))
            cursor = end
    return result


def timestamp(seconds: float, separator: str = ",") -> str:
    ms = round(seconds * 1000)
    hours, ms = divmod(ms, 3600000)
    minutes, ms = divmod(ms, 60000)
    sec, ms = divmod(ms, 1000)
    return f"{hours:02}:{minutes:02}:{sec:02}{separator}{ms:03}"


def subtitles(segments: list[Segment], work: Path) -> None:
    for ext, sep in [("srt", ","), ("vtt", ".")]:
        content = "WEBVTT\n\n" if ext == "vtt" else ""
        for i, seg in enumerate(segments, 1):
            content += f"{i}\n{timestamp(seg.start, sep)} --> {timestamp(seg.end, sep)}\n{seg.text}\n\n"
        (work / f"subtitles.{ext}").write_text(content, encoding="utf-8")


def tempo_filters(ratio: float) -> str:
    filters = []
    while ratio > 2:
        filters.append("atempo=2")
        ratio /= 2
    while ratio < .5:
        filters.append("atempo=0.5")
        ratio *= 2
    return ",".join([*filters, f"atempo={ratio:.9f}"])


def timeline(segments: list[Segment], clips: list[Path], total: float, work: Path) -> Path:
    """Write PCM incrementally; memory use does not grow with video length."""
    rate = 24000
    path = work / "dubbing.wav"
    with wave.open(str(path), "wb") as output:
        output.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        cursor = 0
        def silence(samples: int):
            while samples > 0:
                count = min(samples, rate)
                output.writeframesraw(b"\0\0" * count)
                samples -= count
        for i, (seg, clip) in enumerate(zip(segments, clips, strict=True)):
            start, end = round(seg.start * rate), round(seg.end * rate)
            silence(max(0, start - cursor))
            slot = (end - start) / rate
            # Speed up long utterances to fit; retain natural speed for short ones.
            ratio = max(1.0, duration(clip) / slot)
            fitted = work / f"fitted-{i:05}.wav"
            ffmpeg("-i", str(clip), "-af", f"{tempo_filters(ratio)},apad,atrim=duration={slot:.9f}", "-ar", str(rate), "-ac", "1", "-c:a", "pcm_s16le", str(fitted))
            with wave.open(str(fitted), "rb") as input_audio:
                data = input_audio.readframes(end - start)
                output.writeframesraw(data)
                silence(end - start - len(data) // 2)
            fitted.unlink()
            cursor = end
        silence(max(0, round(total * rate) - cursor))
    return path


def mux(video: Path, audio: Path | None, srt: Path | None, language: str, total: float, output: Path) -> None:
    args = ["-i", str(video)]
    if audio:
        args += ["-i", str(audio)]
    if srt:
        args += ["-i", str(srt)]
    args += ["-map", "0:v:0", "-map", "1:a:0" if audio else "0:a:0?", "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-c:a", "aac"]
    if audio:
        args += ["-metadata:s:a:0", f"language={language}"]
    if srt:
        args += ["-map", "2:0" if audio else "1:0", "-c:s", "mov_text", "-metadata:s:s:0", f"language={language}", "-disposition:s:0", "default"]
    ffmpeg(*args, "-t", str(total), "-movflags", "+faststart", str(output))


def save_segments(path: Path, segments: list[Segment]):
    path.write_text(json.dumps([asdict(s) for s in segments], ensure_ascii=False, indent=2), encoding="utf-8")
