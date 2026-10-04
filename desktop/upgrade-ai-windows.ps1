param([string]$Model = 'qwen2.5:7b-instruct')
$ErrorActionPreference = 'Stop'
try {
    $configPath = Join-Path $env:LOCALAPPDATA 'GrantFiller\installation.json'
    if (-not (Test-Path $configPath)) { throw 'Finish Setup Windows first, then run this update.' }
    $config = Get-Content -Raw $configPath | ConvertFrom-Json
    & $config.python (Join-Path $PSScriptRoot 'model_upgrade.py') --model $Model
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} catch {
    Write-Host "AI UPDATE NEEDS ATTENTION: $_" -ForegroundColor Red
    exit 1
}
