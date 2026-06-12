"""Utilidades de texto compartidas por las herramientas.

Todas las funciones son deterministas y locales (sin red, sin LLM):
las herramientas producen EVIDENCIA verificable; la síntesis generativa
es responsabilidad de los agentes.
"""
from __future__ import annotations

import re
from collections import Counter

from app.security.sanitization import normalize_for_matching

# Stopwords mínimas ES/EN para extracción de keywords.
STOPWORDS: frozenset[str] = frozenset(
    """
    a al algo ante antes como con contra cual cuando de del desde donde dos el
    ella ellas ellos en entre era erais eran eras eres es esa esas ese eso esos
    esta estaba estado estamos estan estar este esto estos fue fueron ha haber
    habia han hasta hay la las le les lo los mas me mi mientras muy nada ni no
    nos nosotros nuestra nuestro o os otra otro para pero poco por porque que
    quien se sea segun ser si sin sobre son su sus tambien tanto te tiene tienen
    todo todos tras tu un una uno unos ya yo
    the a an and or but if then else when at by for with about against between
    into through during before after above below to from up down in out on off
    over under again further once here there all any both each few more most
    other some such only own same so than too very can will just should now is
    are was were be been being have has had do does did of it its this that
    these those as not what which who whom
    """.split()
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n{2,}")
_WORD = re.compile(r"[a-záéíóúüñ0-9][a-záéíóúüñ0-9\-_.]{1,}", re.IGNORECASE)

# Números en formato europeo (1.234,56) o anglosajón (1,234.56) o simple.
# La primera alternativa exige al menos un separador de miles para no
# capturar solo los 3 primeros dígitos de cifras planas largas (40000).
_NUMBER = re.compile(r"-?\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?|-?\d+(?:[.,]\d+)?")


def split_sentences(text: str) -> list[str]:
    """Divide texto en frases de forma aproximada (sin NLP pesado)."""
    if not text:
        return []
    parts = _SENTENCE_SPLIT.split(text.strip())
    return [p.strip() for p in parts if p and p.strip()]


def tokenize(text: str) -> list[str]:
    """Tokens normalizados (minúsculas, sin acentos), sin stopwords."""
    normalized = normalize_for_matching(text or "")
    return [t for t in _WORD.findall(normalized) if t not in STOPWORDS and len(t) >= 3]


def top_keywords(text: str, n: int = 10) -> list[tuple[str, int]]:
    """Palabras clave más frecuentes con su número de apariciones."""
    return Counter(tokenize(text)).most_common(n)


def extractive_summary(text: str, max_sentences: int = 5) -> list[str]:
    """Resumen extractivo: frases mejor puntuadas por frecuencia de términos.

    Determinista y citable: cada frase devuelta existe literalmente en el
    texto original (no se genera contenido nuevo).
    """
    sentences = split_sentences(text)
    if len(sentences) <= max_sentences:
        return sentences

    frequencies = Counter(tokenize(text))
    scored: list[tuple[float, int, str]] = []
    for idx, sentence in enumerate(sentences):
        tokens = tokenize(sentence)
        if not tokens:
            continue
        score = sum(frequencies[t] for t in tokens) / (len(tokens) ** 0.5)
        # Pequeño bonus a las primeras frases (suelen contener el contexto).
        if idx < 2:
            score *= 1.25
        scored.append((score, idx, sentence))

    best = sorted(scored, key=lambda item: -item[0])[:max_sentences]
    return [sentence for _score, _idx, sentence in sorted(best, key=lambda item: item[1])]


def parse_number(raw: str) -> float | None:
    """Convierte '1.234,56', '1,234.56', '1234.5' o '1234' a float."""
    raw = (raw or "").strip()
    if not raw:
        return None
    match = _NUMBER.fullmatch(raw) or _NUMBER.search(raw)
    if not match:
        return None
    value = match.group(0)
    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")  # europeo
        else:
            value = value.replace(",", "")  # anglosajón
    elif "," in value:
        # Una sola coma: decimal europeo salvo que parezca separador de miles.
        head, _, tail = value.rpartition(",")
        if len(tail) == 3 and head and "." not in head:
            value = value.replace(",", "")
        else:
            value = value.replace(",", ".")
    try:
        return float(value)
    except ValueError:
        return None


def text_stats(text: str) -> dict[str, int]:
    """Métricas básicas y verificables de un texto."""
    lines = (text or "").splitlines()
    return {
        "chars": len(text or ""),
        "words": len((text or "").split()),
        "lines": len(lines),
        "sentences": len(split_sentences(text or "")),
    }


def make_snippet(text: str, term: str, width: int = 280) -> str:
    """Extrae un fragmento del texto centrado en la primera aparición del término."""
    if not text:
        return ""
    normalized_text = normalize_for_matching(text)
    normalized_term = normalize_for_matching(term)
    pos = normalized_text.find(normalized_term) if normalized_term else -1
    if pos < 0:
        return text[:width].strip()
    start = max(0, pos - width // 3)
    end = min(len(text), pos + (2 * width) // 3)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{text[start:end].strip()}{suffix}"
