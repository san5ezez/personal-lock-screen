$runKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
Remove-ItemProperty -Path $runKey -Name "PersonalLockScreen" -ErrorAction SilentlyContinue
Write-Host "Startup removed for the current Windows user."
