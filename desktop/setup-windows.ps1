$ErrorActionPreference = 'Stop'
function Get-Python {
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe",
        "$env:ProgramFiles\Python312\python.exe"
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) { return $candidate }
    }
    foreach ($name in @('python', 'python3')) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command -and $command.Source -notlike '*\WindowsApps\*') {
            try {
                & $command.Source -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" 2>$null
                if ($LASTEXITCODE -eq 0) { return $command.Source }
            } catch { }
        }
    }
    return $null
}
try {
    $python = Get-Python
    if (-not $python) {
        if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
            Start-Process 'https://www.python.org/downloads/windows/'
            throw 'Install Python 3.12 or newer from the opened page, then run Setup again.'
        }
        Write-Host 'Installing Python. Approve the installer if prompted.'
        & winget install --id Python.Python.3.12 --exact --source winget --scope user --accept-package-agreements --accept-source-agreements
        $python = Get-Python
        if (-not $python) { throw 'Python was not found. Finish its installer and run Setup again.' }
    }
    $ollama = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
    if (-not (Test-Path $ollama) -and -not (Get-Command ollama -ErrorAction SilentlyContinue)) {
        if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
            Start-Process 'https://ollama.com/download/windows'
            throw 'Install Ollama from the opened page, then run Setup again.'
        }
        Write-Host 'Installing Ollama. Approve the installer if prompted.'
        & winget install --id Ollama.Ollama --exact --source winget --accept-package-agreements --accept-source-agreements
    }
    & $python (Join-Path $PSScriptRoot 'setup.py')
    if ($LASTEXITCODE -ne 0) { throw 'Setup did not finish. Read the error above, fix it, and run Setup again.' }
} catch {
    Write-Host "SETUP NEEDS ATTENTION: $_" -ForegroundColor Red
    exit 1
}
