#!/bin/bash

export DISPLAY=:0
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8
export PYTHONIOENCODING=utf-8
export QT_QPA_PLATFORM=xcb
export SDL_VIDEODRIVER=x11
export PATH=/home/weafon/.espressif/python_env/idf5.5_py3.12_env/bin/:$PATH

# 2. 指定 YouTube 載入工具（強烈建議使用 yt-dlp）
# 如果你安裝的是 yt-dlp，請加上這一行：
export MPV_YTDL_EXE="yt-dlp"
source ~/.my.env
cd ~/aiwindow
# 1. 清理舊的 Socket
rm -f /tmp/mpvsocket
# 2. 啟動 mpv 並開啟 IPC 功能 (背景執行)
echo "啟動窗景播放器 (idle mode)..."
# 啟動 mpv 空閒模式，之後由 ai_window.py 隨機選取並下達 loadfile 指令
mpv --idle --fs --input-ipc-server=/tmp/mpvsocket &
MPV_PID=$!
echo "MPV PID: $MPV_PID"

# 3. 啟動 AI UI
echo "啟動 AI UI..."
python3 ai_window.py

# 4. 當 UI 結束時，清理後台進程
echo "UI finished. Killing MPV PID: $MPV_PID"
kill $MPV_PID
echo "Kill command sent."
