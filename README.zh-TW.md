# AI Window 助手 (Gemini Live 版)

AI Window 是一款極簡的透明視窗助手，結合了即時語音互動與沉浸式背景場景。由 Gemini Live 與 YouTube 驅動，讓您只需透過語音指令即可變換您的工作空間。

## 🌟 特色功能

- **即時語音互動**：使用 `gemini-2.5-flash-native-audio-preview` 進行雙向串流。
- **智慧場景切換**：根據對話關鍵字自動搜尋並播放 YouTube 4K 窗景影片（例如「倫敦雨天」、「瑞士阿爾卑斯山」）。
- **智慧音訊管理**：
  - **自動暫停**：開始與 AI 對話時，背景音樂/影片會自動暫停。
  - **自動恢復**：對話結束後，背景音訊會無縫恢復播放。
  - **抖動緩衝 (Jitter Buffer)**：先進的延遲管理，防止網路波動造成的音訊斷斷續續。
- **極簡 UI**：優雅、透明且「始終置頂」的 PyQt6 介面。
- **自動關閉麥克風**：偵測到搜尋指令後，助手會在 6 秒後自動關閉麥克風，使其能完成口頭確認。

## 🛠️ 預備條件

- **Python 3.10+**
- **FFmpeg**：音訊處理所需。
- **MPV**：背景影片播放所需。
- **yt-dlp**：搜尋 YouTube 內容所需。
- **相關依賴**：
  ```bash
  pip install PyQt6 google-genai nest_asyncio
  ```

## 🚀 安裝與啟動

1. **獲取 Gemini API Key**：訪問 [Google AI Studio](https://aistudio.google.com/) 獲取您的金鑰。
2. **設定環境變數**：
   ```bash
   export GEMINI_API_KEY='您的金鑰'
   ```
3. **啟動應用程式**：
   一切都已透過啟動腳本自動化。只需執行：
   ```bash
   chmod +x start_window.sh
   ./start_window.sh
   ```
   *此腳本將自動清理先前的 socket、在背景啟動 MPV 並播放預設的雨景、啟動 AI 介面，並在退出時清理程序。*

## 🖥️ 桌面捷徑 (Ubuntu)

`aiwin.desktop` 檔案讓您可以在 Ubuntu 桌面上點擊一下即可啟動 AI Window。

1.  **配置路徑**：打開 `aiwin.desktop` 並更新 `Exec` 與 `Icon` 路徑，使其指向您本地的專案目錄（例如：將 `/home/weafon/aiwindow/` 替換為您的實際路徑）。
2.  **部署**：將檔案複製到您的桌面：
    ```bash
    cp aiwin.desktop ~/Desktop/
    ```
3.  **權限**：在桌面上的檔案點擊右鍵，選擇 **"Allow Launching" (允許啟動)**。

## 🎙️ 使用方式

- **語音指令**：點擊 🎤 按鈕開始 Live 對話。
- **切換場景**：告訴 AI 類似這樣的話：
  - *「我想看倫敦雨天的街道。」*
  - *「給我看雪山的景色。」*
  - *「幫我換成日本街道的風景。」*
- **文字輸入**：您也可以在底部的輸入框輸入指令。
- **結束**：點擊 '✕' 或按下 `Esc`。

## 🌐 Chrome 擴充功能 (send2mpv)

`send2mpv` 擴充功能讓您可以將 Chrome 中正在觀看的 YouTube 影片網址直接傳送到 AI Window 進行遠端播放。

1.  **安裝**：
    - 開啟 Chrome 並前往 `chrome://extensions/`。
    - 開啟右上角的 **「開發者模式」**。
    - 點擊 **「載入解壓縮擴充功能」** 並選擇此專案中的 `send2mpv` 目錄。
2.  **配置**：
    - 開啟 `send2mpv/background.js`。
    - 更新 `targetIp` 為執行 AI Window 的電腦 IP 位址。
    - (選填) 如果您更改了預設埠 (9998)，請更新 `targetPort`。
3.  **使用**：
    - 在 YouTube 影片頁面上點擊擴充功能圖示，即可將其傳送至 AI Window。本地影片將自動暫停。

## ⚙️ 技術細節

- **音訊配置**：
  - 錄音：16kHz, 16-bit PCM。
  - 播放：24kHz, 16-bit PCM (Gemini Live 輸出的標準格式)。
- **抖動緩衝 (Jitter Buffer)**：具備 5 秒的突發容忍度與 20ms 的檢查間隔，確保不論網路狀況如何都能流暢播放。
- **設備選擇**：自動優先選擇外部麥克風（如 USB 音訊、會議攝像頭）以獲得更好的語音品質。

## 📝 授權

此專案僅供展示與個人使用。由 Google Gemini 驅動。
