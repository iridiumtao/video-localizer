from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

from .media import Segment

# Translation code, Edge voice and ISO 639-2 code used in MP4 metadata.
LANGUAGES = {
    "ja": ("ja-JP-NanamiNeural", "jpn"),
    "en": ("en-US-JennyNeural", "eng"),
    "zh-TW": ("zh-TW-HsiaoChenNeural", "zho"),
    "zh-CN": ("zh-CN-XiaoxiaoNeural", "zho"),
    "ko": ("ko-KR-SunHiNeural", "kor"),
    "es": ("es-ES-ElviraNeural", "spa"),
    "fr": ("fr-FR-DeniseNeural", "fra"),
    "de": ("de-DE-KatjaNeural", "deu"),
    "it": ("it-IT-ElsaNeural", "ita"),
    "pt": ("pt-BR-FranciscaNeural", "por"),
}


class Providers:
    def __init__(self, model: str = "small", device: str = "cpu", voice: str | None = None, translation_model: Path | None = None):
        self.model, self.device, self.voice = model, device, voice
        self.translation_model = translation_model
        self.source_language = None

    def transcribe(self, audio: Path) -> tuple[list[Segment], str]:
        from faster_whisper import WhisperModel
        model = WhisperModel(self.model, device=self.device, compute_type="int8" if self.device == "cpu" else "float16")
        segments, info = model.transcribe(str(audio), vad_filter=True, beam_size=5)
        self.source_language = info.language
        return [Segment(s.start, s.end, s.text) for s in segments], info.language

    def translate(self, segments: list[Segment], target: str) -> list[Segment]:
        if self.translation_model:
            from .local_translation import translate
            return translate(segments, target, self.translation_model, self.source_language)
        from deep_translator import GoogleTranslator
        translator = GoogleTranslator(source="auto", target=target)
        result = []
        for seg in segments:
            # Google's free endpoint has a 5000-character limit per request.
            if len(seg.text) >= 5000:
                raise ValueError("單一字幕超過翻譯服務字數限制")
            for attempt in range(3):
                try:
                    text = translator.translate(seg.text)
                    if not text or not text.strip():
                        raise RuntimeError("翻譯服務傳回空文字")
                    result.append(Segment(seg.start, seg.end, text))
                    break
                except Exception:
                    if attempt == 2:
                        raise
                    time.sleep(attempt + 1)
        return result

    def synthesize(self, text: str, target: str, path: Path) -> None:
        import edge_tts
        ca_bundle = os.environ.get("VIDEO_LOCALIZER_CA_BUNDLE")
        if ca_bundle:
            # Edge TTS 7 explicitly passes its own certifi SSL context to
            # ws_connect. Add the configured CA without disabling verification.
            import edge_tts.communicate
            edge_tts.communicate._SSL_CTX.load_verify_locations(cafile=ca_bundle)
        async def generate():
            # aiohttp does not inherit proxy settings automatically.
            proxy = os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY")
            for attempt in range(3):
                try:
                    await edge_tts.Communicate(text, self.voice or LANGUAGES[target][0], proxy=proxy).save(str(path))
                    if not path.stat().st_size:
                        raise RuntimeError("配音服務未回傳音訊")
                    return
                except Exception:
                    if attempt == 2:
                        raise
                    await asyncio.sleep(attempt + 1)
        asyncio.run(generate())
