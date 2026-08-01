# LocalScribe setup for Windows. Run from the repo root in PowerShell.
$ErrorActionPreference = "Stop"

Write-Host "== LocalScribe setup ==" -ForegroundColor Cyan

# 1. Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Installing Python 3.11 via winget..."
    winget install -e --id Python.Python.3.11 --accept-source-agreements --accept-package-agreements
    Write-Host "Python installed. CLOSE this window, open a NEW PowerShell, and re-run setup.ps1" -ForegroundColor Yellow
    exit 0
}

# 2. Venv + dependencies
if (-not (Test-Path ".venv")) { python -m venv .venv }
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m spacy download en_core_web_md

# 3. Ollama + Gemma
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "Installing Ollama via winget..."
    winget install -e --id Ollama.Ollama --accept-source-agreements --accept-package-agreements
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}
Write-Host "Pulling gemma3:4b (~3.3 GB, one time)..."
ollama pull gemma3:4b

# 4. Pre-download Whisper model
Write-Host "Downloading Whisper small.en model (one time)..."
.venv\Scripts\python -c "from faster_whisper import WhisperModel; WhisperModel('small.en', device='cpu', compute_type='int8')"

# 5. Smoke test
Write-Host "Running self-test..."
.venv\Scripts\python -m src.selftest

# 6. Desktop shortcut
.\make_shortcut.ps1

Write-Host "== Done. Double-click the LocalScribe icon on the Desktop. ==" -ForegroundColor Green
