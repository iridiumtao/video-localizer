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

## GitHub：初次嘗試未建立遠端 repo（歷史紀錄）

初次嘗試時，已配置的 `gh` 執行 `gh api user --jq .login` 回傳 `HTTP 401 Bad credentials`。沒有使用無效憑證繼續建立遠端 repo，也沒有推送。需恢復 GitHub 授權後才能發佈。原始碼與本機 Git 歷史均已保留。

可於完成授權後自行建立私人遠端：

```bash
cd video-localizer
gh repo create video-localizer --private --source=. --remote=origin --push
```

## 後續實測更新：真實語音流程已通過

最初的 16 項隔離測試不足以驗證外部服務。本次已完成 **12.2 秒測試影片** 的真實辨識、翻譯、日文配音與字幕封裝：

1. 使用 Edge TTS 產生英文語音，封裝為明確標示 `SYNTHETIC TEST FIXTURE` 的來源影片。
2. 實際執行 Whisper base / CPU / int8，辨識出 3 段英文語音。
3. 使用 Argos 官方英日 CTranslate2 模型實際翻譯 3 段文字。
4. 使用 Edge TTS Nanami 實際產生日文語音，對齊原時間軸。
5. 封裝 H.264 / AAC / mov_text MP4，音軌與字幕皆標示 `jpn`。
6. 從完成的 MP4 抽回字幕，確認 3 段日文文字完整保留。
7. 將完成的配音重新交由 Whisper 辨識，得到日文語句，確認輸出不是原英文音軌或空音訊。

可查閱 [流程紀錄](live-e2e.log)、[完成狀態](live-e2e-manifest.json)、[驗證結果](live-e2e-verification.json)、[原文](live-e2e-transcript.json)、[譯文](live-e2e-translation.json)。測試影片是合成素材，**不是使用者指定的 YouTube 影片**。

本次實測找到並修復兩個問題：

- PyAV 19 與 faster-whisper 1.2.1 不相容：限制 `av<19`，實際使用 18.1.1。新增真實音訊解碼回歸測試，目前 **17 passed**。
- Edge TTS 使用獨立 certifi SSL context：新增 `VIDEO_LOCALIZER_CA_BUNDLE`，載入環境提供的可信 CA 後成功配音。TLS 驗證保持啟用。Google 翻譯仍回傳 429，因此以本機模型完成翻譯。

### 指定 YouTube 影片依然受環境限制

已進一步查明，環境設定工具雖回報 unrestricted，**即時代理政策的 denylist 明列 `youtube.com` 與 `googlevideo.com`，並包含子網域**。這與先前 CONNECT 403 的實際結果一致。這不是 yt-dlp 參數、JavaScript runtime 或登入 cookies 能修正的問題；尚未存取到影片頁或影音資料。

精簡政策證據：[youtube-network-policy.json](youtube-network-policy.json)。未嘗試繞過封鎖。需取得使用者提供的影片檔，或在正式允許存取 YouTube 的執行環境，才能完成指定影片的實測；本次不宣稱該影片已完成。
