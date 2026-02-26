#!/bin/bash

export DISPLAY=:0
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8
export PYTHONIOENCODING=utf-8
export QT_QPA_PLATFORM=xcb
export SDL_VIDEODRIVER=x11
# 1. 清理舊的 Socket
rm -f /tmp/mpvsocket

# 2. 啟動 mpv 並開啟 IPC 功能 (背景執行)
# 預設先播京都雨天
echo "啟動窗景播放器..."
mpv --fs --loop=inf --input-ipc-server=/tmp/mpvsocket "https://www.youtube.com/watch?v=akUYfKwlo0E" 2> /dev/null &
MPV_PID=$!

# 3. 啟動 AI UI
echo "啟動 AI UI..."
python3 ai_window.py

# 4. 當 UI 結束時，清理後台進程
kill $MPV_PID
