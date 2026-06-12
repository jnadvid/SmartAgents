"""Herramientas financieras: cálculo determinista de magnitudes básicas.

La herramienta extrae cifras etiquetadas de texto libre o las recibe
directamente, y calcula márgenes, punto de equilibrio y escenarios simples.
No es asesoramiento financiero.
"""
from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from app.security.sanitization import normalize_for_matching
from app.tools._text_utils import parse_number
from app.tools.base import BaseTool, ToolContext

_AMOUNT = r"([-+]?\d[\d.,]*)"

_LABEL_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "revenue": [
        re.compile(rf"(?:ingresos?|ventas?|facturacion|revenue)\D{{0,20}}{_AMOUNT}"),
    ],
    "fixed_costs": [
        re.compile(rf"(?:costes? fijos?|costos? fijos?|fixed costs?)\D{{0,20}}{_AMOUNT}"),
    ],
    "variable_costs": [
        re.compile(rf"(?:costes? variables?|costos? variables?|variable costs?)\D{{0,20}}{_AMOUNT}"),
    ],
    "total_costs": [
        re.compile(rf"(?:costes? totales?|costos? totales?|gastos? totales?|total costs?)\D{{0,20}}{_AMOUNT}"),
        re.compile(rf"(?:costes?|costos?|gastos?)\D{{0,20}}{_AMOUNT}"),
    ],
    "unit_price": [
        re.compile(rf"(?:precio unitario|precio por unidad|precio|unit price)\D{{0,20}}{_AMOUNT}"),
    ],
    "unit_variable_cost": [
        re.compile(rf"(?:coste variable unitario|costo variable unitario|coste por unidad)\D{{0,20}}{_AMOUNT}"),
    ],
    "units": [
        re.compile(rf"(?:unidades|clientes|suscripciones|licencias|units)\D{{0,20}}{_AMOUNT}"),
    ],
}


def _extract_amounts(text: str) -> dict[str, float]:
    normalized = normalize_for_matching(text)
    found: dict[str, float] = {}
    for label, patterns in _LABEL_PATTERNS.items():
        for pattern in patterns:
            match = pattern.search(normalized)
            if match:
                # El final de frase puede colarse en la captura ("40000."):
                # se recorta cualquier separador colgante antes de parsear.
                value = parse_number(match.group(1).rstrip(".,"))
                if value is not None:
                    found[label] = value
                    break
    return found


class CalculateBasicFinancialsInput(BaseModel):
    text: str | None = Field(default=None, max_length=50000, description="Texto con cifras etiquetadas")
    revenue: float | None = Field(default=None, ge=0)
    fixed_costs: float | None = Field(default=None, ge=0)
    variable_costs: float | None = Field(default=None, ge=0)
    unit_price: float | None = Field(default=None, ge=0)
    unit_variable_cost: float | None = Field(default=None, ge=0)


class CalculateBasicFinancialsTool(BaseTool):
    name = "calculate_basic_financials"
    category = "finance"
    description = (
        "Extrae cifras financieras etiquetadas (ingresos, costes, precios) de "
        "texto o parámetros y calcula margen, punto de equilibrio y escenarios ±10%."
    )
    input_schema = CalculateBasicFinancialsInput
    timeout_seconds = 10

    def execute(self, payload: CalculateBasicFinancialsInput, ctx: ToolContext) -> dict[str, Any]:
        extracted = _extract_amounts(payload.text or "")

        revenue = payload.revenue if payload.revenue is not None else extracted.get("revenue")
        fixed_costs = payload.fixed_costs if payload.fixed_costs is not None else extracted.get("fixed_costs")
        variable_costs = (
            payload.variable_costs if payload.variable_costs is not None else extracted.get("variable_costs")
        )
        total_costs_extracted = extracted.get("total_costs")
        unit_price = payload.unit_price if payload.unit_price is not None else extracted.get("unit_price")
        unit_variable_cost = (
            payload.unit_variable_cost
            if payload.unit_variable_cost is not None
            else extracted.get("unit_variable_cost")
        )

        if fixed_costs is not None or variable_costs is not None:
            total_costs: float | None = (fixed_costs or 0.0) + (variable_costs or 0.0)
        else:
            total_costs = total_costs_extracted

        results: dict[str, Any] = {}
        missing: list[str] = []

        if revenue is not None and total_costs is not None:
            margin = revenue - total_costs
            results["gross_margin"] = round(margin, 2)
            results["margin_pct"] = round((margin / revenue) * 100, 2) if revenue else None
            results["scenarios"] = {
                "revenue_minus_10pct": round(revenue * 0.9 - total_costs, 2),
                "revenue_plus_10pct": round(revenue * 1.1 - total_costs, 2),
                "costs_plus_10pct": round(revenue - total_costs * 1.1, 2),
            }
        else:
            if revenue is None:
                missing.append("ingresos (revenue)")
            if total_costs is None:
                missing.append("costes totales o fijos+variables")

        if fixed_costs is not None and unit_price is not None and unit_variable_cost is not None:
            contribution = unit_price - unit_variable_cost
            if contribution > 0:
                results["break_even_units"] = round(fixed_costs / contribution, 1)
            else:
                results["break_even_units"] = None
                results["break_even_note"] = "El margen de contribución unitario es <= 0."

        return {
            "inputs_used": {
                "revenue": revenue,
                "fixed_costs": fixed_costs,
                "variable_costs": variable_costs,
                "total_costs": total_costs,
                "unit_price": unit_price,
                "unit_variable_cost": unit_variable_cost,
            },
            "extracted_from_text": extracted,
            "results": results,
            "missing_data": missing,
            "disclaimer": "Cálculo orientativo; no constituye asesoramiento financiero profesional.",
        }
