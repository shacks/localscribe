# LocalScribe

Fully local consultation recorder for clinicians. One button to record, local
Whisper transcription, two-pass local PHI redaction (Presidio + Gemma audit),
output as a plain text file named by date and time. Nothing ever leaves the
machine: no cloud APIs, no accounts, no telemetry.

## How it works

1. Click **Start Recording** at the beginning of a consult, **Stop** at the end.
2. The audio drops into a background queue; you can immediately record the next
   consult while the previous one processes.
3. Pipeline per recording (all local, run sequentially to fit in 8 GB RAM):
   - **Transcribe**: faster-whisper (`small.en`, int8, CPU). Model is unloaded
     before the next stage.
   - **Redact pass 1 (deterministic)**: Microsoft Presidio with spaCy NER plus
     custom recognizers for Ontario health card numbers, SIN, Canadian postal
     codes, phone numbers, emails. Reproducible, catches the bulk.
   - **Redact pass 2 (LLM audit)**: Gemma 3 4B via Ollama reads the already
     redacted text and returns ONLY a JSON list of remaining identifying spans
     (nicknames, contextual identifiers). The code does the replacement; the
     LLM never rewrites the transcript, so clinical content cannot be silently
     altered.
4. Output: `Documents\LocalScribe\Transcripts\2026-08-01 14-30 consult.txt`.
   The filename timestamp is the re-linking key against the clinic schedule.
5. The raw WAV is deleted after a successful transcript (configurable). The
   audio is the biggest privacy liability; the redacted text is nearly
   harmless.

## Install (on the target Windows machine)

Open this folder in Claude Code and say "install LocalScribe per CLAUDE.md",
or run manually in PowerShell (as a normal user):

```powershell
.\setup.ps1
```

This installs Python 3.11 (winget), a venv with dependencies, the spaCy model,
Ollama, pulls `gemma3:4b`, pre-downloads the Whisper model, and puts a
**LocalScribe** shortcut on the Desktop.

Optionally build a standalone exe afterwards:

```powershell
.\build_exe.ps1
```

## Configuration

`config.json` next to the app (created from `config.default.json` on first
run):

| Key | Default | Notes |
|---|---|---|
| `whisper_model` | `small.en` | Set `medium.en` for better accuracy, ~2-3x slower on this CPU |
| `ollama_model` | `gemma3:4b` | LLM audit model |
| `llm_audit` | `true` | Set `false` to skip pass 2 (output is flagged accordingly) |
| `delete_audio_after_success` | `true` | Keep `true` unless debugging |
| `output_dir` | `~/Documents/LocalScribe/Transcripts` | Keep OUT of OneDrive sync |
| `open_for_review` | `true` | Opens each transcript in Notepad when ready |

## Privacy and professional obligations (Ontario / PHIPA)

- Obtain and note patient consent to record at the start of each consult.
- Spot-check redacted output before pasting into any AI tool, especially the
  first weeks. No local redaction pipeline is perfect; the header of each file
  reminds you.
- Keep the output folder out of cloud sync (OneDrive/Google Drive).
- Filenames are quasi-identifying by design (date+time re-links to the
  schedule); treat the folder as sensitive even though each file reads
  anonymous.

## Hardware target

Tuned for a 13th-gen Intel i7 U-series (12 threads), Intel Xe iGPU, 8 GB RAM,
CPU-only inference. A 15-minute consult takes roughly 4-8 minutes to
transcribe with `small.en` plus 1-3 minutes for the Gemma audit. Close heavy
apps (many Chrome tabs) if processing feels slow.
