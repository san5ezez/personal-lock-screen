$ErrorActionPreference = "Stop"

$baseDir = $PSScriptRoot
$shellScript = Join-Path $baseDir "winlogon_shell.py"
$backupFile = Join-Path $baseDir "winlogon_shell_backup.txt"
$pythonw = Get-Command pythonw.exe -ErrorAction SilentlyContinue
if (-not $pythonw) {
    $pythonw = Get-Command python.exe -ErrorAction Stop
}

$key = "HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Winlogon"
$oldShell = (Get-ItemProperty -Path $key -Name Shell -ErrorAction SilentlyContinue).Shell
if ($null -eq $oldShell) { $oldShell = "" }
Set-Content -LiteralPath $backupFile -Value $oldShell -Encoding UTF8

$shellCommand = '"' + $pythonw.Source + '" "' + $shellScript + '"'
Set-ItemProperty -Path $key -Name Shell -Value $shellCommand

# The old Run entry is no longer needed and could launch a second lock screen.
$runKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
Remove-ItemProperty -Path $runKey -Name "PersonalLockScreen" -ErrorAction SilentlyContinue
Write-Host "Winlogon shell installed for the current Windows user. Restart Windows to test."
