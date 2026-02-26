@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: --- 設定區 ---
set "UBUNTU_IP=10.144.1.98"
set "PORT=9998"
:: --------------

echo ========================================
echo       遠端 MPV 傳送器 (穩定修復版)
echo ========================================

set "URL=%~1"

:: 如果沒有拖曳東西，嘗試從剪貼簿獲取
if "!URL!" == "" (
    for /f "usebackq tokens=*" %%a in (`powershell -NoProfile -Command "Get-Clipboard -Raw"`) do set "CLIP_URL=%%a"
    if not "!CLIP_URL!" == "" (
        echo 偵測到剪貼簿內容: !CLIP_URL!
        set /p "CHOICE=是否使用此網址播放? (Y/n): "
        if /i "!CHOICE!" == "Y" set "URL=!CLIP_URL!"
        if /i "!CHOICE!" == "" set "URL=!CLIP_URL!"

    )
)

:: 如果還是空的，請使用者手動輸入
if "!URL!" == "" (
    set /p "URL=請貼上網址或拖曳檔案到此處: "
)

if "!URL!" == "" (
    echo [錯誤] 沒有輸入網址，程式結束。
    timeout /t 10
    exit
)

echo.
echo 🚀 正在傳送至 !UBUNTU_IP!:!PORT! ...
#    "$json = '{\"command\":[\"loadfile\",\"' + $url + '\",\"replace\"]}';" ^
:: 這次我們將所有邏輯縮減成一個乾淨的 PowerShell 字串
powershell -NoProfile -Command ^
    "$url = '!URL!'.Trim();" ^
	"$json = @{ command = @('loadfile', $url) } | ConvertTo-Json -Compress; " ^
	"echo $json;" ^
    "try {" ^
    "  $client = New-Object System.Net.Sockets.TcpClient('%UBUNTU_IP%', %PORT%);" ^
    "  $stream = $client.GetStream();" ^
    "  $writer = New-Object System.IO.StreamWriter($stream);" ^
    "  $writer.AutoFlush = $true;" ^
    "  $writer.Write($json);" ^
    "  Start-Sleep -Milliseconds 100;" ^
    "  $client.Close();" ^
    "  Write-Host '✅ 成功傳送！' -ForegroundColor Green;" ^
    "} catch {" ^
    "  Write-Host '❌ 錯誤：無法連線到 Ubuntu。' -ForegroundColor Red;" ^
    "  Write-Host $_.Exception.Message -ForegroundColor Yellow;" ^
    "  exit 1;" ^
    "}"

echo.
echo 視窗將在 10 秒後自動關閉...
timeout /t 30