@echo off
cd /d "%~dp0"
:: Silently register cert if present
if exist "PixelPieMedia_RootCA.cer" (
    certutil -user -addstore -f "TrustedPublisher" "PixelPieMedia_RootCA.cer" >nul 2>&1
)
:: Launch SDM silently
start "" "%~dp0SDM.exe"
exit
