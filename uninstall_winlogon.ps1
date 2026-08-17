$ErrorActionPreference = "Stop"

$key = "HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Winlogon"
$backupFile = Join-Path $PSScriptRoot "winlogon_shell_backup.txt"
$oldShell = ""
if (Test-Path -LiteralPath $backupFile) {
    $oldShell = (Get-Content -LiteralPath $backupFile -Raw).Trim()
}

if ([string]::IsNullOrWhiteSpace($oldShell)) {
    Remove-ItemProperty -Path $key -Name Shell -ErrorAction SilentlyContinue
} else {
    Set-ItemProperty -Path $key -Name Shell -Value $oldShell
}

Write-Host "Winlogon shell restored. Restart Windows to return to the normal desktop."
