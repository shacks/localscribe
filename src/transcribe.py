"""Local transcription with faster-whisper. The model is loaded per call and
freed afterwards so RAM is available for the redaction LLM (8 GB machine)."""
import gc


def transcribe(wav_path: str, model_name: str, compute_type: str = "int8") -> str:
    from faster_whisper import WhisperModel

    model = WhisperModel(model_name, device="cpu", compute_type=compute_type)
    segments, _info = model.transcribe(
        wav_path, language="en", vad_filter=True, beam_size=5
    )
    lines = [seg.text.strip() for seg in segments if seg.text.strip()]
    del model
    gc.collect()
    return "\n".join(lines)
