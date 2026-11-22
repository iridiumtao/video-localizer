# 驗證報告

日期：2026-11-22（UTC）

## 已完成

- 新建本機 Git repository：`video-localizer`，分支 `main`。
- Python CLI 安裝成功，`video-localizer --help` 正常。
- 自動測試：**16 passed**（Python 3.12 / FFmpeg 7.1.5）。
- 三種模式的媒體整合測試均使用真實 FFmpeg 產生與讀取影片，確認 MP4 內字幕文字、日文語言標記、配音長度與初始靜音、截取與防覆寫。
- 官方 API 後端的測試驗證分批翻譯保持時間軸、拒絕無效回應及缺少 key。這些是注入測試回應，不是實際 API 連線。

## 使用者指定影片：未完成

```bash
video-localizer 'https://www.youtube.com/watch?v=teC0t1JDzeA' \
  --language ja --mode both --output outputs/verification-ja
```

實際執行 exit code = 1。環境代理於 YouTube CONNECT 階段回覆 `403 Forbidden`；錯誤包含 `Tunnel connection failed: 403 Forbidden`。程式記錄 `status=failed`、`failed_stage=acquire`。沒有下載到來源，沒有辨識、翻譯或生成該影片的日文配音與字幕。

原始紀錄：[requested-run.log](requested-run.log)、[requested-manifest.json](requested-manifest.json)。

## 外部服務測試

- Google 翻譯：實際請求 `Hello, welcome to the video.` → `ja`，服務回傳 TooManyRequests（限流）。
- Edge TTS：實際請求日文語音時發生 `ClientConnectorCertificateError`，憑證鏈含無法驗證的自簽憑證。未停用 TLS 驗證。
- OpenAI：環境沒有 `OPENAI_API_KEY`，未做實際連線測試。
- Whisper：尚未進行真實語音辨識／模型下載驗證；自動測試使用注入的辨識結果。

因此，本報告不宣稱外部服務端到端成功。免費服務需在可連線、具有效憑證且未限流的環境執行；或配置官方 OpenAI API 後端。YouTube 受阻時可改用有權使用的本機影片。

## GitHub：未建立遠端 repo

已配置的 `gh` 執行 `gh api user --jq .login` 回傳 `HTTP 401 Bad credentials`。沒有使用無效憑證繼續建立遠端 repo，也沒有推送。需恢復 GitHub 授權後才能發佈。原始碼與本機 Git 歷史均已保留。

可於完成授權後自行建立私人遠端：

```bash
cd video-localizer
gh repo create video-localizer --private --source=. --remote=origin --push
```
