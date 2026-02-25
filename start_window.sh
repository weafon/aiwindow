#!/bin/bash

export DISPLAY=:0
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8
export PYTHONIOENCODING=utf-8
export QT_QPA_PLATFORM=xcb
export SDL_VIDEODRIVER=x11
# 1. 清理舊的 Socket
rm -f /tmp/mpvsocket
rm -f /home/weafon/.gemini/tmp/ec81af70508adebcba9dafaa5d302b0e8893f236fa9994eb1ef1ea1255a8bf83/mpv.log

# 2. 啟動 mpv 並開啟 IPC 功能 (背景執行)
# 預設先播京都雨天
echo "啟動窗景播放器..."
export url="https://www.youtube.com/watch?v=ROgRn3WuLN0"
#export url="https://www.youtube.com/watch?v=akUYfKwlo0E"
mpv --idle --fs --loop=inf --input-ipc-server=/tmp/mpvsocket $url &
MPV_PID=$!
echo "MPV PID: $MPV_PID"

# 3. 啟動 AI UI
echo "啟動 AI UI..."
python3 ai_window.py

# 4. 當 UI 結束時，清理後台進程
echo "UI finished. Killing MPV PID: $MPV_PID"
kill $MPV_PID
echo "Kill command sent."
