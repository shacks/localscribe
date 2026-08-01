# Optional: build a standalone exe with PyInstaller.
# If the exe misbehaves (PyInstaller + spaCy can be fragile), use the Desktop
# shortcut from make_shortcut.ps1 instead - same user experience.
$ErrorActionPreference = "Stop"
.venv\Scripts\pip install pyinstaller
.venv\Scripts\pyinstaller --noconfirm --windowed --name LocalScribe `
    --collect-all faster_whisper `
    --collect-all ctranslate2 `
    --collect-all presidio_analyzer `
    --collect-all presidio_anonymizer `
    --collect-all spacy `
    --collect-all en_core_web_md `
    --collect-all thinc `
    --collect-all srsly `
    --collect-all blis `
    --collect-all sounddevice `
    --collect-all soundfile `
    run.py
Copy-Item config.default.json dist\LocalScribe\
Write-Host "Built dist\LocalScribe\LocalScribe.exe" -ForegroundColor Green
Write-Host "Test the exe before pointing the Desktop shortcut at it."
