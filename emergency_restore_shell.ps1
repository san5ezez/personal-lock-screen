$ErrorActionPreference = "SilentlyContinue"

Stop-Process -Name "winlogon_shell" -Force
Set-ItemProperty `
  -Path "HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Winlogon" `
  -Name "Shell" `
  -Value "explorer.exe"
Start-Process "explorer.exe"
Write-Host "Explorer restored for the current Windows user."
