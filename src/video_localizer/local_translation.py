"""Translate timestamped utterances using an extracted Argos CT2 package."""
import json
from pathlib import Path

from .media import Segment


def translate(segments: list[Segment], target: str, model: Path, source_language: str | None = None) -> list[Segment]:
    import ctranslate2
    try:
        import sentencepiece
    except ImportError as exc:
        raise RuntimeError("請安裝本機翻譯依賴：pip install -e '.[local]'") from exc
    metadata = json.loads((model / "metadata.json").read_text(encoding="utf-8"))
    if metadata.get("to_code") != target:
        raise ValueError("翻譯模型的目標語言與指定輸出語言不符")
    if source_language and metadata.get("from_code") != source_language:
        raise ValueError(f"翻譯模型來源為 {metadata.get('from_code')}，影片語言為 {source_language}")
    tokenizer = sentencepiece.SentencePieceProcessor(model_file=str(model / "sentencepiece.model"))
    translator = ctranslate2.Translator(str(model / "model"), device="cpu", compute_type="int8")
    result = []
    for segment in segments:
        tokens = tokenizer.encode(segment.text, out_type=str)
        if len(tokens) > 384:
            raise ValueError("片段超過本機模型的安全長度，請改用 API 翻譯")
        translated = translator.translate_batch([tokens], beam_size=4, max_decoding_length=512)[0]
        text = tokenizer.decode(translated.hypotheses[0]).strip()
        if not text:
            raise RuntimeError("本機翻譯模型回傳空譯文")
        result.append(Segment(segment.start, segment.end, text))
    return result
