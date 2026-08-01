"""Two-pass PHI redaction.

Pass 1 (deterministic): Presidio + spaCy NER + custom Canadian recognizers.
Pass 2 (LLM audit): Gemma via Ollama nominates remaining identifying spans as
JSON; Python does the replacement. The LLM never rewrites transcript text, so
clinical content cannot be silently altered.
"""
import gc
import json
import re

import requests

PLACEHOLDERS = {
    "PERSON": "[NAME]",
    "PHONE_NUMBER": "[PHONE]",
    "EMAIL_ADDRESS": "[EMAIL]",
    "LOCATION": "[LOCATION]",
    "CA_HEALTH_CARD": "[HEALTH-CARD]",
    "CA_SIN": "[SIN]",
    "CA_POSTAL_CODE": "[POSTAL-CODE]",
    "URL": "[URL]",
    "IP_ADDRESS": "[IP]",
}


def _build_analyzer():
    from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
    from presidio_analyzer.nlp_engine import NlpEngineProvider

    provider = NlpEngineProvider(
        nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_md"}],
        }
    )
    analyzer = AnalyzerEngine(nlp_engine=provider.create_engine(), supported_languages=["en"])

    custom = [
        ("CA_HEALTH_CARD", r"\b\d{4}[- ]?\d{3}[- ]?\d{3}[- ]?[A-Za-z]{0,2}\b", 0.6),
        ("CA_SIN", r"\b\d{3}[- ]\d{3}[- ]\d{3}\b", 0.6),
        ("CA_POSTAL_CODE", r"\b[A-Za-z]\d[A-Za-z][ -]?\d[A-Za-z]\d\b", 0.7),
    ]
    for name, regex, score in custom:
        analyzer.registry.add_recognizer(
            PatternRecognizer(
                supported_entity=name,
                patterns=[Pattern(name=name.lower(), regex=regex, score=score)],
            )
        )
    return analyzer


def presidio_redact(text: str) -> str:
    from presidio_anonymizer import AnonymizerEngine
    from presidio_anonymizer.entities import OperatorConfig

    analyzer = _build_analyzer()
    results = analyzer.analyze(
        text=text, language="en", entities=list(PLACEHOLDERS.keys()), score_threshold=0.4
    )
    operators = {
        entity: OperatorConfig("replace", {"new_value": placeholder})
        for entity, placeholder in PLACEHOLDERS.items()
    }
    redacted = AnonymizerEngine().anonymize(text=text, analyzer_results=results, operators=operators).text
    del analyzer
    gc.collect()
    return redacted


AUDIT_PROMPT = """You are a privacy auditor. Below is a medical consultation transcript that has already had obvious identifiers replaced with placeholders like [NAME].

List any REMAINING text spans that could identify the patient or their family: names or nicknames, employers, schools, street or place names, unique events, ages combined with rare conditions, or anything similar. Copy each span EXACTLY as it appears in the text.

Do NOT list: medical conditions, symptoms, medications, dosages, or existing [PLACEHOLDER] tokens.

Respond with JSON only: {{"identifiers": ["span1", "span2"]}}. Use an empty list if nothing remains.

TRANSCRIPT:
{chunk}"""


def _ollama_audit_chunk(chunk: str, url: str, model: str) -> list[str]:
    resp = requests.post(
        f"{url}/api/generate",
        json={
            "model": model,
            "prompt": AUDIT_PROMPT.format(chunk=chunk),
            "format": "json",
            "stream": False,
            "options": {"temperature": 0.0, "num_ctx": 8192},
            "keep_alive": 0,
        },
        timeout=900,
    )
    resp.raise_for_status()
    data = json.loads(resp.json()["response"])
    spans = data.get("identifiers", [])
    return [s for s in spans if isinstance(s, str)]


def llm_audit_redact(text: str, url: str, model: str, chunk_words: int = 1200) -> tuple[str, int]:
    """Returns (redacted_text, spans_removed). Raises on Ollama failure."""
    words = text.split(" ")
    chunks = [
        " ".join(words[i : i + chunk_words]) for i in range(0, len(words), chunk_words)
    ]
    spans: set[str] = set()
    for chunk in chunks:
        spans.update(_ollama_audit_chunk(chunk, url, model))

    removed = 0
    for span in sorted(spans, key=len, reverse=True):
        span = span.strip()
        # ignore hallucinated, trivial, or placeholder-shaped nominations
        if len(span) < 3 or span.startswith("[") or span not in text:
            continue
        text = text.replace(span, "[REDACTED]")
        removed += 1
    return text, removed


def ollama_available(url: str) -> bool:
    try:
        return requests.get(f"{url}/api/tags", timeout=5).ok
    except requests.RequestException:
        return False
