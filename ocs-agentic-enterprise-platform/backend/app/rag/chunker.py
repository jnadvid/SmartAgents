"""División de texto en chunks para indexado y recuperación."""
from __future__ import annotations

from app.config import get_settings


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[str]:
    """Divide texto en chunks de ~chunk_size caracteres respetando párrafos.

    - Une párrafos hasta acercarse a chunk_size.
    - Los párrafos enormes se trocean con solape para no perder contexto.
    """
    settings = get_settings()
    size = chunk_size or settings.rag_chunk_size
    over = overlap if overlap is not None else settings.rag_chunk_overlap
    over = min(over, size // 2)

    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > size:
            if current:
                chunks.append(current)
                current = ""
            start = 0
            while start < len(paragraph):
                piece = paragraph[start : start + size]
                chunks.append(piece.strip())
                if start + size >= len(paragraph):
                    break
                start += size - over
            continue

        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) <= size:
            current = candidate
        else:
            chunks.append(current)
            # Solape: arrastra el final del chunk anterior para dar contexto.
            tail = current[-over:] if over else ""
            current = f"{tail}\n\n{paragraph}".strip() if tail else paragraph

    if current:
        chunks.append(current)

    return [c for c in (chunk.strip() for chunk in chunks) if c]
