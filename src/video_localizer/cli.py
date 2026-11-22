import argparse
import logging
from pathlib import Path

from .pipeline import process
from .providers import LANGUAGES


def positive_seconds(value):
    import math
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("秒數必須為正數")
    return number


def main():
    parser = argparse.ArgumentParser(description="影片翻譯：YouTube 或影片檔 → 指定語言配音 / 字幕")
    parser.add_argument("source", help="YouTube HTTPS URL 或本機影片路徑")
    parser.add_argument("--language", choices=LANGUAGES, default="ja")
    parser.add_argument("--mode", choices=["both", "dub", "subtitles"], default="both")
    parser.add_argument("--output", type=Path, required=True, help="新的輸出資料夾")
    parser.add_argument("--model", default="small", help="Whisper 模型名稱或本機模型資料夾")
    parser.add_argument("--provider", choices=["free", "openai"], default="free", help="翻譯與配音服務；openai 需 API key，辨識仍在本機")
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    parser.add_argument("--voice", help="自訂 Edge TTS voice ID")
    parser.add_argument("--cookies", type=Path, help="YouTube Netscape cookies 檔案（不會提交至 Git）")
    parser.add_argument("--max-seconds", type=positive_seconds, help="僅處理前 N 秒；預設整部影片")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        result = process(**vars(args))
    except KeyboardInterrupt:
        parser.exit(130, "\n處理已中止\n")
    except Exception as exc:
        parser.exit(1, f"處理失敗：{exc}\n")
    print(result)


if __name__ == "__main__":
    main()
