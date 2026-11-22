# Video Localizer

輸入 **YouTube 連結或本機影片檔案**，輸出指定語言的 **自動配音、字幕或兩者**。本專案提供 Python CLI；影片檔案以路徑輸入。

流程：yt-dlp 下載 → FFmpeg 抽音軌 → faster-whisper 本機語音辨識 → Google 翻譯 → Edge TTS → 時間軸對齊 → MP4 封裝。

## 安裝

需要 Python 3.11+、FFmpeg / ffprobe，以及網路連線。Linux 可用 `sudo apt install ffmpeg`；macOS 可用 `brew install ffmpeg`。

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

首次使用會自動下載 Whisper 模型至 Hugging Face 快取；CPU 預設 `small` / int8。可用 `--model base` 加速，或 `--device cuda` 使用已備妥 CUDA/cuDNN 的 GPU。模型也可指定本機資料夾。

## 指定影片：日文自動配音 + 字幕

```bash
video-localizer 'https://www.youtube.com/watch?v=teC0t1JDzeA' \
  --language ja --mode both --output outputs/teC0t1JDzeA-ja
```

本機影片、只產生字幕、只產生配音：

```bash
video-localizer './input.mp4' --language ja --mode both --output outputs/local-ja
video-localizer './input.mp4' --language en --mode subtitles --output outputs/en-subs
video-localizer './input.mp4' --language ko --mode dub --output outputs/ko-dub
```

支援語言：`ja`、`en`、`zh-TW`、`zh-CN`、`ko`、`es`、`fr`、`de`、`it`、`pt`。`--voice ja-JP-KeitaNeural` 可選日文男聲；日文預設 Nanami。`--max-seconds 30` 僅處理前 30 秒，未指定則處理整部影片。每次需使用新的或空的輸出資料夾，以免覆寫成果。

## 輸出

- `localized.mp4`：H.264/AAC 影片，both 模式附預設開啟的日文字幕軌。播放器需支援 MP4 可切換字幕，例如 VLC；字幕不是燒錄在畫面中。
- `subtitles.srt` / `subtitles.vtt`：UTF-8 字幕（both / subtitles）。
- `dubbing.wav`：與原影片等長的單聲道配音（both / dub）。
- `transcript.json` / `translation.json`：附時間戳的原文與譯文。
- `manifest.json`：來源、設定、處理階段與成功／失敗狀態。
- 中間音檔及 YouTube 下載來源保留於輸出資料夾，可在完成後自行刪除。

字幕模式保留原音軌；配音模式以合成配音取代原音軌，因此不會保留原本背景音樂。不做聲音複製或嘴形同步。較長的譯文會加速到原字幕時段內，較短則以靜音補齊；極短時段或冗長譯文可能影響自然度。字幕與配音品質取決於辨識、翻譯結果，正式使用前應人工校對。

## 服務與存取

預設不需要付費 API key，但 Google 翻譯與 Edge TTS 使用的公開端點不是具有 SLA 的商用 API，可能限流或變更。辨識在本機執行；原文會傳至 Google 翻譯，譯文會傳至 Microsoft Edge TTS。服務錯誤會停止處理並記錄 failed，不會以假字幕或靜音冒充成功。

YouTube 可能要求登入、拒絕機器人或限制地區。可用 `--cookies /path/to/youtube-cookies.txt` 傳入自己匯出的 Netscape cookies；請勿提交憑證。直播、播放清單與非 YouTube URL 不支援。請只處理有權使用的影片。此工具適合個人命令列操作，不應直接暴露為未驗證的公網服務。

環境代理設定會由下載／翻譯服務繼承，TTS 亦會傳入 `HTTPS_PROXY`。若環境政策封鎖 YouTube，需要在允許下載的環境執行，或改用已取得的本機影片。

## 測試

```bash
pytest -q
```

測試以注入的辨識／翻譯／配音測試服務隔離網路，**實際執行 FFmpeg**，驗證三種輸出模式、字幕封裝與文字、配音時長與初始靜音、截取、失敗狀態和防止覆寫。測試配音使用正弦波，不是實際日文語音；不代表外部服務端到端通過。

指定影片的環境實測狀態見 [reports/validation.md](reports/validation.md)。

## 可選：官方 OpenAI API

若免費服務不可用，可安裝官方 API 後端。辨識仍使用本機 Whisper；翻譯使用 `gpt-4o-mini`，配音使用 `tts-1`，費用由你的 API 帳戶支付。原文與譯文會傳送至 OpenAI。環境變數請透過安全方式設定，不要寫入 Git。

```bash
pip install -e '.[openai]'
# 先設定 OPENAI_API_KEY
video-localizer './input.mp4' --language ja --mode both \
  --provider openai --voice alloy --output outputs/openai-ja
```

此環境沒有 OpenAI API key，官方後端尚未進行連線實測。

## 本機翻譯與代理憑證

Google 翻譯限流時，可用 Argos 官方 CTranslate2 模型離線翻譯。下列英日模型需約 115 MB，模型僅適用英文來源與日文輸出；程式會驗證辨識出的語言是否符合模型。

```bash
pip install -e '.[local]'
mkdir -p .cache/argos
curl -fL https://argos-net.com/v1/translate-en_ja-1_1.argosmodel \
  -o .cache/argos/en-ja.argosmodel
python -m zipfile -e .cache/argos/en-ja.argosmodel .cache/argos
video-localizer './input.mp4' --language ja --mode both \
  --translation-model .cache/argos/en_ja --output outputs/local-model-ja
```

若網路使用企業或管理型代理，可將 `VIDEO_LOCALIZER_CA_BUNDLE` 指向其可信 PEM CA 檔案，讓 Edge TTS 在原有信任鏈上載入它；TLS 憑證驗證仍啟用。不要使用來路不明的 CA。

真實外部服務流程測試（合成英文來源影片、實際 Whisper／本機翻譯／日文 TTS）：

```bash
python scripts/live_smoke.py --translation-model .cache/argos/en_ja \
  --model base --output outputs/live-smoke
```

此命令需要 Edge TTS 連線，與不需網路的 `pytest` 測試不同。已完成的實測資料見 [驗證結果](reports/live-e2e-verification.json)。此測試素材並非指定的 YouTube 影片。

## 日文配音示範

[下載示範 MP4](examples/synthetic-ja-demo.mp4) · [日文 SRT](examples/synthetic-ja-demo.srt)。這是 12.2 秒合成英文來源影片經真實辨識、翻譯與日文配音產生的結果，並非使用者指定的 YouTube 影片。MP4 內含可切換日文字幕軌，建議用 VLC 播放。
