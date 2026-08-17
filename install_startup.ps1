$ErrorActionPreference = "Stop"

$scriptPath = Join-Path $PSScriptRoot "lock_screen.py"
$pythonw = Get-Command pythonw.exe -ErrorAction SilentlyContinue
if (-not $pythonw) {
    $pythonw = Get-Command python.exe -ErrorAction Stop
}

$command = '"' + $pythonw.Source + '" "' + $scriptPath + '"'
$runKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
Set-ItemProperty -Path $runKey -Name "PersonalLockScreen" -Value $command
Write-Host "Startup installed for the current Windows user."
