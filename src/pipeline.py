"""Post-recording pipeline: transcribe -> redact pass 1 -> redact pass 2 -> save.

Stages run sequentially and free their models between stages so peak RAM stays
within an 8 GB machine.
"""
import os
from datetime import datetime
from pathlib import Path

from . import redact, transcribe


def process(wav_path: str, started_at: datetime, cfg: dict, status_cb=lambda msg: None) -> str:
    """Runs the full pipeline. Returns the transcript path."""
    stamp = started_at.strftime("%Y-%m-%d %H-%M")
    out_path = Path(cfg["output_dir"]) / f"{stamp} consult.txt"

    status_cb(f"{stamp}: transcribing...")
    raw = transcribe.transcribe(wav_path, cfg["whisper_model"], cfg["whisper_compute_type"])
    if not raw.strip():
        raise RuntimeError("empty transcript (no speech detected)")

    status_cb(f"{stamp}: redacting (pass 1, Presidio)...")
    redacted = redact.presidio_redact(raw)
    del raw

    audit_note = "LLM audit: disabled in config"
    if cfg["llm_audit"]:
        if redact.ollama_available(cfg["ollama_url"]):
            status_cb(f"{stamp}: redacting (pass 2, LLM audit)...")
            redacted, removed = redact.llm_audit_redact(
                redacted, cfg["ollama_url"], cfg["ollama_model"]
            )
            audit_note = f"LLM audit: complete ({removed} additional spans removed)"
        else:
            audit_note = "LLM audit: SKIPPED (Ollama not running) - review extra carefully"

    header = (
        f"# LocalScribe transcript\n"
        f"# Recorded: {started_at.strftime('%Y-%m-%d %H:%M')}\n"
        f"# Redaction: Presidio pass complete. {audit_note}\n"
        f"# REVIEW BEFORE SHARING with any AI tool or third party.\n\n"
    )
    out_path.write_text(header + redacted, encoding="utf-8")

    if cfg["delete_audio_after_success"]:
        os.remove(wav_path)
    return str(out_path)
