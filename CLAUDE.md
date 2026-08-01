# LocalScribe — instructions for Claude Code on the target machine

You are installing LocalScribe on a clinician's Windows laptop (13th-gen i7
U-series, 8 GB RAM, CPU-only). The user is non-technical; do everything
yourself and verify each step before moving on.

## Install steps

1. **Python 3.11+**: check `python --version`. If missing:
   `winget install -e --id Python.Python.3.11` (then restart the shell so PATH
   updates).
2. **Venv + deps** (from the repo root):
   ```powershell
   python -m venv .venv
   .venv\Scripts\pip install --upgrade pip
   .venv\Scripts\pip install -r requirements.txt
   .venv\Scripts\python -m spacy download en_core_web_md
   ```
3. **Ollama**: `winget install -e --id Ollama.Ollama`, restart shell, then
   `ollama pull gemma3:4b`. Verify with `ollama run gemma3:4b "say ok"` (first
   token is slow on CPU; be patient, allow ~2 minutes).
4. **Pre-download the Whisper model** so first real use is not slow:
   ```powershell
   .venv\Scripts\python -c "from faster_whisper import WhisperModel; WhisperModel('small.en', device='cpu', compute_type='int8')"
   ```
5. **Smoke test**: `.venv\Scripts\python -m src.selftest` — records nothing;
   it synthesizes a tiny WAV, runs the full pipeline, and prints PASS/FAIL per
   stage. Fix anything that fails before continuing.
6. **Desktop shortcut**: run `.\make_shortcut.ps1`. This creates a
   "LocalScribe" Desktop shortcut that launches the app windowless via
   `pythonw.exe`. This is the reliable default "exe experience".
7. **Optional real exe**: `.\build_exe.ps1` builds `dist\LocalScribe\LocalScribe.exe`
   with PyInstaller. If the exe fails to start (PyInstaller + spaCy can be
   fragile), keep the shortcut from step 6 — same user experience.
8. **Output folder**: ensure `Documents\LocalScribe\Transcripts` exists and is
   NOT inside a OneDrive-synced path. If her Documents folder is
   OneDrive-redirected, change `output_dir` in `config.json` to a local path
   like `C:\LocalScribe\Transcripts` and tell the user you did so.

## Constraints to respect

- 8 GB RAM: never load Whisper and Gemma simultaneously. The pipeline already
  runs them sequentially and unloads Whisper first; do not "optimize" this.
- Everything must stay local. Do not add any cloud API, telemetry, or
  network call other than `localhost:11434` (Ollama).
- The LLM audit must never rewrite transcript text. It only nominates spans;
  Python does the replacement. Do not change this design.
- Do not commit or sync any recordings or transcripts; `.gitignore` already
  excludes them.

## Troubleshooting

- `sounddevice` errors: check Windows microphone privacy settings
  (Settings > Privacy > Microphone > allow desktop apps).
- Ollama connection refused: `ollama serve` should run as a service after
  install; start the Ollama app once if needed.
- Out-of-memory during Gemma audit: close browser windows, or set
  `"llm_audit": false` in config.json (files are then flagged
  "LLM audit skipped" in their header).
