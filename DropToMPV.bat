@echo off
setlocal enabledelayedexpansion

:: Check if URL is provided
set "URL=%~1"
if "!URL!"=="" (
    echo Usage: Drop a URL or a shortcut onto this file to play it on the Ubuntu AI Window.
    echo.
    set /p "URL=Or enter URL manually: "
    if "!URL!"=="" exit /b
)

:: --- CONFIGURATION ---
:: Replace this with the actual IP address of your Ubuntu machine
:: You can find it by running 'hostname -I' on your Ubuntu computer.
set "UBUNTU_IP=192.168.1.100"
set "PORT=9999"
:: ---------------------

echo Sending URL to !UBUNTU_IP!:!PORT!...
echo !URL!

:: Use an environment variable to pass the URL to PowerShell to avoid escaping issues (like '&' in YouTube URLs)
set "REMOTE_URL=!URL!"
powershell -Command "$url = [System.Environment]::GetEnvironmentVariable('REMOTE_URL', 'Process'); $client = New-Object System.Net.Sockets.TcpClient('!UBUNTU_IP!', !PORT!); $stream = $client.GetStream(); $writer = New-Object System.IO.StreamWriter($stream); $writer.Write($url); $writer.Flush(); $client.Close()"

if %ERRORLEVEL% equ 0 (
    echo Success!
) else (
    echo.
    echo Failed to send URL.
    echo Please check the IP address (!UBUNTU_IP!) and ensure the AI Window is running on Ubuntu.
    pause
)
