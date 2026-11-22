from __future__ import annotations

import json
import logging
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .media import acquire, duration, ffmpeg, mux, normalize, save_segments, subtitles, timeline
from .providers import LANGUAGES, Providers

log = logging.getLogger(__name__)


def process(source: str, output: Path, language: str = "ja", mode: str = "both", *, providers=None, provider="free", model="small", device="cpu", voice=None, cookies=None, max_seconds: float | None = None, translation_model: Path | None = None) -> Path:
    if language not in LANGUAGES or mode not in {"both", "dub", "subtitles"} or provider not in {"free", "openai"}:
        raise ValueError("不支援的語言或輸出模式")
    if max_seconds is not None and (not math.isfinite(max_seconds) or max_seconds <= 0):
        raise ValueError("max-seconds 必須大於零")
    if translation_model and provider != "free":
        raise ValueError("本機翻譯模型僅適用於 free provider")
    for binary in ("ffmpeg", "ffprobe"):
        if not shutil.which(binary):
            raise RuntimeError(f"請先安裝 {binary}")
    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("輸出資料夾不是空的，請選擇新資料夾")
    output.mkdir(parents=True, exist_ok=True)
    manifest = {"source": source, "language": language, "mode": mode, "model": model, "voice": voice or LANGUAGES[language][0], "max_seconds": max_seconds, "started_at": datetime.now(timezone.utc).isoformat(), "status": "running"}
    def status(stage):
        manifest["stage"] = stage
        (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info(stage)
    manifest.update(provider=provider, voice=voice or ("alloy" if provider == "openai" else LANGUAGES[language][0]))
    manifest["translation_model"] = str(translation_model) if translation_model else None
    try:
        status("initialize")
        if provider == "openai" and providers is None:
            from .openai_provider import OpenAIProviders
            services = OpenAIProviders(model, device, voice)
        else:
            services = providers or Providers(model, device, voice, translation_model)
        status("acquire")
        video = acquire(source, output, cookies)
        total = duration(video)
        if not math.isfinite(total) or total <= 0:
            raise ValueError("無效的影片長度")
        if max_seconds:
            total = min(total, max_seconds)
        status("transcribe")
        audio = output / "source.wav"
        ffmpeg("-i", str(video), "-t", str(total), "-vn", "-ac", "1", "-ar", "16000", str(audio))
        original, source_language = services.transcribe(audio)
        original = normalize(original, total)
        if not original:
            raise RuntimeError("未偵測到語音，無法產生字幕或配音")
        save_segments(output / "transcript.json", original)
        manifest.update(source_language=source_language, duration=total, segments=len(original))
        status("translate")
        translated = normalize(services.translate(original, language), total)
        if len(translated) != len(original):
            raise RuntimeError("翻譯結果缺少字幕片段")
        save_segments(output / "translation.json", translated)
        srt = None
        if mode in {"both", "subtitles"}:
            subtitles(translated, output)
            srt = output / "subtitles.srt"
        narration = None
        if mode in {"both", "dub"}:
            status("synthesize")
            clips = []
            for i, seg in enumerate(translated):
                clip = output / f"voice-{i:05}.mp3"
                services.synthesize(seg.text, language, clip)
                clips.append(clip)
                log.info("配音 %s/%s", i + 1, len(translated))
            status("align")
            narration = timeline(translated, clips, total, output)
        status("mux")
        result = output / "localized.mp4"
        mux(video, narration, srt, LANGUAGES[language][1], total, result)
        manifest.update(status="completed", result=result.name)
        status("completed")
        return result
    except Exception as exc:
        manifest.update(status="failed", failed_stage=manifest["stage"], error=str(exc))
        status("failed")
        raise
