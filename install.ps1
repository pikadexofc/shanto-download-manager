# Shanto Download Manager (SDM) Zero-Friction One-Line Web Installer
$ErrorActionPreference = "Stop"

Write-Host "`n========================================================" -ForegroundColor Cyan
Write-Host "  Installing Shanto Download Manager by PixelPie Media  " -ForegroundColor Cyan
Write-Host "========================================================`n" -ForegroundColor Cyan

$installDir = "$env:LOCALAPPDATA\Programs\SDM"
New-Item -ItemType Directory -Path $installDir -Force | Out-Null

$zipUrl = "https://github.com/pikadexofc/shanto-download-manager/releases/download/v1.0.0/SDM-v1.0.0-windows-x64.zip"
$zipPath = "$env:TEMP\SDM-v1.0.0.zip"

Write-Host "[1/4] Fetching latest release package..." -ForegroundColor Yellow
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13
Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath

Write-Host "[2/4] Deploying to $installDir..." -ForegroundColor Yellow
Expand-Archive -Path $zipPath -DestinationPath $installDir -Force
Remove-Item $zipPath -Force

Write-Host "[3/4] Registering PixelPie Media security certificate..." -ForegroundColor Yellow
$cert = "$installDir\PixelPieMedia_RootCA.cer"
if (Test-Path $cert) {
    certutil -user -addstore -f "TrustedPublisher" $cert | Out-Null
}

Write-Host "[4/4] Creating Desktop Shortcut..." -ForegroundColor Yellow
$wsh = New-Object -ComObject WScript.Shell
$sc = $wsh.CreateShortcut("$([Environment]::GetFolderPath('Desktop'))\Shanto Download Manager.lnk")
$sc.TargetPath = "$installDir\SDM.exe"
$sc.WorkingDirectory = $installDir
$sc.Save()

Write-Host "`n[DONE] Installation Complete! Launching Shanto Download Manager..." -ForegroundColor Green
Start-Process "$installDir\SDM.exe"
