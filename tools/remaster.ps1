# Python is an official external dependency; this wrapper changes no execution policy.
# Example: .\tools\remaster.ps1 diagnose --game-dir 'D:\SteamLibrary\steamapps\common\Need for Speed Undercover'
$ErrorActionPreference = 'Stop'
$scriptPath = Join-Path $PSScriptRoot 'remaster.py'
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 $scriptPath @args
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python $scriptPath @args
} else {
    Write-Error 'Install Python 3.10+ from https://www.python.org/downloads/windows/ and enable its launcher.'
    exit 2
}
exit $LASTEXITCODE
