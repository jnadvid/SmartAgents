"""Herramientas de análisis de datos sobre texto tabular (CSV/TSV/Markdown)."""
from __future__ import annotations

import csv
import io
import statistics
from typing import Any

from pydantic import BaseModel, Field

from app.tools._text_utils import parse_number
from app.tools.base import BaseTool, ToolContext, ToolError

_MAX_ROWS = 5000
_MAX_COLUMNS = 50


def _detect_delimiter(sample: str) -> str:
    """Detecta el delimitador más probable de un texto tabular."""
    candidates = {"\t": 0, ";": 0, ",": 0, "|": 0}
    for line in sample.splitlines()[:10]:
        for delim in candidates:
            candidates[delim] += line.count(delim)
    best = max(candidates, key=lambda d: candidates[d])
    return best if candidates[best] > 0 else ","


def _parse_rows(text: str) -> tuple[list[str], list[list[str]]]:
    """Parsea texto tabular y devuelve (cabeceras, filas)."""
    cleaned_lines = [
        line for line in text.strip().splitlines() if line.strip() and not set(line.strip()) <= {"|", "-", " ", ":"}
    ]
    if not cleaned_lines:
        raise ToolError("No se encontraron filas de datos en el texto.")

    delimiter = _detect_delimiter("\n".join(cleaned_lines[:10]))
    reader = csv.reader(io.StringIO("\n".join(cleaned_lines)), delimiter=delimiter)
    rows = [[cell.strip() for cell in row] for row in reader]
    rows = [row for row in rows if any(cell for cell in row)]
    if delimiter == "|":
        rows = [[cell for cell in row if cell != ""] for row in rows]
    if len(rows) < 2:
        raise ToolError("Se necesitan al menos una cabecera y una fila de datos.")
    if len(rows) > _MAX_ROWS + 1:
        rows = rows[: _MAX_ROWS + 1]

    header_candidate = rows[0]
    header_is_text = sum(1 for cell in header_candidate if parse_number(cell) is None) >= max(
        1, len(header_candidate) // 2
    )
    if header_is_text:
        headers = [cell or f"col_{i + 1}" for i, cell in enumerate(header_candidate)]
        data_rows = rows[1:]
    else:
        headers = [f"col_{i + 1}" for i in range(len(header_candidate))]
        data_rows = rows

    return headers[:_MAX_COLUMNS], [row[:_MAX_COLUMNS] for row in data_rows]


def _column_values(data_rows: list[list[str]], index: int) -> list[str]:
    return [row[index] if index < len(row) else "" for row in data_rows]


class AnalyzeTableTextInput(BaseModel):
    text: str = Field(min_length=3, max_length=200000, description="CSV/TSV o tabla pegada")


class AnalyzeTableTextTool(BaseTool):
    name = "analyze_table_text"
    category = "data"
    description = (
        "Analiza texto tabular (CSV, TSV, tabla Markdown): estadísticas por "
        "columna, valores faltantes y anomalías numéricas (IQR)."
    )
    input_schema = AnalyzeTableTextInput
    timeout_seconds = 20

    def execute(self, payload: AnalyzeTableTextInput, ctx: ToolContext) -> dict[str, Any]:
        headers, data_rows = _parse_rows(payload.text)

        columns: list[dict[str, Any]] = []
        anomalies: list[dict[str, Any]] = []

        for index, header in enumerate(headers):
            raw_values = _column_values(data_rows, index)
            non_empty = [value for value in raw_values if value != ""]
            numbers = [n for n in (parse_number(value) for value in non_empty) if n is not None]
            missing = len(raw_values) - len(non_empty)

            column_info: dict[str, Any] = {
                "name": header,
                "non_empty": len(non_empty),
                "missing": missing,
            }

            if non_empty and len(numbers) >= max(2, int(0.7 * len(non_empty))):
                column_info["type"] = "numeric"
                column_info["stats"] = {
                    "count": len(numbers),
                    "min": round(min(numbers), 4),
                    "max": round(max(numbers), 4),
                    "mean": round(statistics.fmean(numbers), 4),
                    "sum": round(sum(numbers), 4),
                }
                if len(numbers) >= 4:
                    ordered = sorted(numbers)
                    q1 = ordered[len(ordered) // 4]
                    q3 = ordered[(3 * len(ordered)) // 4]
                    iqr = q3 - q1
                    if iqr > 0:
                        low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
                        outliers = [n for n in numbers if n < low or n > high]
                        if outliers:
                            anomalies.append(
                                {
                                    "column": header,
                                    "outlier_count": len(outliers),
                                    "examples": [round(o, 4) for o in outliers[:5]],
                                    "expected_range": [round(low, 4), round(high, 4)],
                                    "method": "IQR x1.5",
                                }
                            )
            else:
                column_info["type"] = "categorical"
                counts: dict[str, int] = {}
                for value in non_empty:
                    counts[value] = counts.get(value, 0) + 1
                top = sorted(counts.items(), key=lambda kv: -kv[1])[:5]
                column_info["top_values"] = [{"value": v[:80], "count": c} for v, c in top]
                column_info["unique_values"] = len(counts)

            columns.append(column_info)

        return {
            "row_count": len(data_rows),
            "column_count": len(headers),
            "truncated": len(data_rows) >= _MAX_ROWS,
            "columns": columns,
            "anomalies": anomalies,
        }
