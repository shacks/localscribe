"""Smoke test for the install: synthesizes a short WAV, runs each pipeline
stage, prints PASS/FAIL. No microphone needed. Run: python -m src.selftest"""
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

from . import config, redact, transcribe

SAMPLE_TEXT = (
    "The patient John Smith, phone 613-555-0199, lives at 12 Main Street, "
    "postal code K1J 8V6. His daughter goes to Riverside Elementary. "
    "He reports chest pain and takes metoprolol 25 mg daily."
)


def check(name, fn):
    try:
        result = fn()
        print(f"PASS  {name}" + (f" -> {result}" if result else ""))
        return True
    except Exception as e:
        print(f"FAIL  {name}: {e}")
        return False


def main():
    cfg = config.load()
    ok = True

    def t_audio():
        # 2 s of silence + tone; just proves whisper loads and runs end to end
        sr = cfg["sample_rate"]
        tone = 0.1 * np.sin(2 * np.pi * 440 * np.linspace(0, 2, 2 * sr))
        wav = Path(tempfile.gettempdir()) / "localscribe_selftest.wav"
        sf.write(wav, tone.astype(np.float32), sr)
        transcribe.transcribe(str(wav), cfg["whisper_model"], cfg["whisper_compute_type"])
        wav.unlink()
        return "whisper model loads and transcribes"

    def t_presidio():
        out = redact.presidio_redact(SAMPLE_TEXT)
        assert "John Smith" not in out, "name not redacted"
        assert "613-555-0199" not in out, "phone not redacted"
        assert "metoprolol" in out, "clinical content was altered"
        return "name/phone redacted, clinical content intact"

    def t_ollama():
        assert redact.ollama_available(cfg["ollama_url"]), "Ollama not reachable"
        out, removed = redact.llm_audit_redact(
            redact.presidio_redact(SAMPLE_TEXT), cfg["ollama_url"], cfg["ollama_model"]
        )
        assert "metoprolol" in out, "clinical content was altered"
        return f"audit ran, {removed} extra spans removed"

    ok &= check("transcription (faster-whisper)", t_audio)
    ok &= check("redaction pass 1 (Presidio)", t_presidio)
    if cfg["llm_audit"]:
        ok &= check("redaction pass 2 (Ollama/Gemma)", t_ollama)

    print("\nALL PASS" if ok else "\nSOME CHECKS FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
