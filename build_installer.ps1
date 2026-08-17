$ErrorActionPreference = "Stop"

$projectDir = $PSScriptRoot
$distDir = Join-Path $projectDir "dist"
$workDir = Join-Path $projectDir "build-pyinstaller"

$pyinstaller = Get-Command pyinstaller -ErrorAction SilentlyContinue
if (-not $pyinstaller) {
    python -c "import PyInstaller" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller is not installed. Run: python -m pip install pyinstaller"
    }
}

$iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if (-not $iscc) {
    $isccPath = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    if (-not (Test-Path -LiteralPath $isccPath)) {
        throw "Inno Setup is not installed. Install it, then run this script again."
    }
} else {
    $isccPath = $iscc.Source
}

Remove-Item -LiteralPath $distDir -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $workDir -Recurse -Force -ErrorAction SilentlyContinue

$pyArgs = @('--noconfirm', '--clean', '--windowed', '--onefile', '--name', 'lock_screen',
    '--distpath', $distDir, '--workpath', $workDir, '--specpath', $workDir)
if ($pyinstaller) {
    & $pyinstaller.Source @pyArgs (Join-Path $projectDir 'lock_screen.py')
} else {
    & python -m PyInstaller @pyArgs (Join-Path $projectDir 'lock_screen.py')
}

$pyArgs = @('--noconfirm', '--clean', '--windowed', '--onefile', '--name', 'winlogon_shell',
    '--distpath', $distDir, '--workpath', $workDir, '--specpath', $workDir)
if ($pyinstaller) {
    & $pyinstaller.Source @pyArgs (Join-Path $projectDir 'winlogon_shell.py')
} else {
    & python -m PyInstaller @pyArgs (Join-Path $projectDir 'winlogon_shell.py')
}

& $isccPath (Join-Path $projectDir "installer.iss")
Write-Host "Installer created in installer-output. Test it before distributing."
