"""Herramientas de compliance: análisis de brechas (gap analysis) simplificado.

Incluye un catálogo reducido y propio de controles de referencia inspirado en
marcos públicos (ISO/IEC 27001:2022 Anexo A y RGPD a alto nivel). Los IDs de
control son referencias públicas de cada marco; las descripciones y la lógica
son propias de esta plataforma.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.security.sanitization import normalize_for_matching
from app.tools.base import BaseTool, ToolContext, ToolError

_FRAMEWORKS: dict[str, dict[str, Any]] = {
    "iso27001": {
        "label": "ISO/IEC 27001:2022 (Anexo A, subconjunto)",
        "controls": [
            {"id": "A.5.1", "name": "Políticas de seguridad de la información", "keywords": ["politica de seguridad", "politicas de seguridad", "security policy"]},
            {"id": "A.5.9", "name": "Inventario de activos", "keywords": ["inventario de activos", "asset inventory", "cmdb"]},
            {"id": "A.5.15", "name": "Control de acceso", "keywords": ["control de acceso", "access control", "gestion de accesos", "rbac"]},
            {"id": "A.5.24", "name": "Gestión de incidentes de seguridad", "keywords": ["gestion de incidentes", "incident response", "respuesta a incidentes"]},
            {"id": "A.5.30", "name": "Continuidad de negocio / TIC", "keywords": ["continuidad", "business continuity", "plan de recuperacion", "disaster recovery", "drp"]},
            {"id": "A.6.3", "name": "Concienciación y formación en seguridad", "keywords": ["concienciacion", "formacion en seguridad", "awareness", "phishing training"]},
            {"id": "A.8.2", "name": "Gestión de privilegios", "keywords": ["privilegios", "privileged access", "pam", "cuentas privilegiadas"]},
            {"id": "A.8.7", "name": "Protección contra malware", "keywords": ["antivirus", "antimalware", "edr", "proteccion contra malware"]},
            {"id": "A.8.8", "name": "Gestión de vulnerabilidades técnicas", "keywords": ["gestion de vulnerabilidades", "vulnerability management", "parcheo", "patching", "escaneo de vulnerabilidades"]},
            {"id": "A.8.13", "name": "Copias de seguridad", "keywords": ["copias de seguridad", "backup", "respaldo"]},
            {"id": "A.8.15", "name": "Registro de eventos (logging)", "keywords": ["logs", "registro de eventos", "logging", "siem", "wazuh"]},
            {"id": "A.8.24", "name": "Uso de criptografía", "keywords": ["cifrado", "criptografia", "encryption", "tls"]},
        ],
    },
    "gdpr": {
        "label": "RGPD/GDPR (obligaciones a alto nivel, subconjunto)",
        "controls": [
            {"id": "Art.30", "name": "Registro de actividades de tratamiento", "keywords": ["registro de actividades", "rat", "records of processing"]},
            {"id": "Art.32", "name": "Medidas técnicas y organizativas", "keywords": ["medidas tecnicas", "seguridad del tratamiento", "cifrado", "pseudonimizacion"]},
            {"id": "Art.33", "name": "Notificación de brechas (72h)", "keywords": ["notificacion de brechas", "breach notification", "72 horas"]},
            {"id": "Art.35", "name": "Evaluación de impacto (EIPD/DPIA)", "keywords": ["evaluacion de impacto", "dpia", "eipd"]},
            {"id": "Art.37", "name": "Delegado de Protección de Datos", "keywords": ["dpo", "delegado de proteccion"]},
            {"id": "Art.28", "name": "Contratos con encargados de tratamiento", "keywords": ["encargado de tratamiento", "data processing agreement", "dpa"]},
            {"id": "Art.13", "name": "Información y transparencia", "keywords": ["politica de privacidad", "informacion al interesado", "transparencia"]},
            {"id": "Art.17", "name": "Derechos de los interesados (supresión, acceso...)", "keywords": ["derechos arco", "derecho de supresion", "derecho de acceso", "data subject rights"]},
        ],
    },
}


class GenerateComplianceGapInput(BaseModel):
    framework: str = Field(
        default="iso27001",
        description="Marco de referencia: iso27001 | gdpr",
        pattern="^(iso27001|gdpr)$",
    )
    implemented_controls_text: str = Field(
        min_length=3,
        max_length=100000,
        description="Descripción libre de los controles/medidas ya implantados",
    )


class GenerateComplianceGapTool(BaseTool):
    name = "generate_compliance_gap"
    category = "compliance"
    description = (
        "Gap analysis simplificado: compara los controles descritos como "
        "implantados con un subconjunto de controles de ISO 27001 o RGPD y "
        "devuelve cobertura, brechas y controles detectados."
    )
    input_schema = GenerateComplianceGapInput
    timeout_seconds = 15

    def execute(self, payload: GenerateComplianceGapInput, ctx: ToolContext) -> dict[str, Any]:
        framework = _FRAMEWORKS.get(payload.framework)
        if framework is None:
            raise ToolError(f"Marco no soportado: {payload.framework}")

        normalized = normalize_for_matching(payload.implemented_controls_text)
        covered: list[dict[str, Any]] = []
        gaps: list[dict[str, Any]] = []

        for control in framework["controls"]:
            hits = [kw for kw in control["keywords"] if kw in normalized]
            entry = {"id": control["id"], "name": control["name"]}
            if hits:
                covered.append({**entry, "matched_keywords": hits})
            else:
                gaps.append(entry)

        total = len(framework["controls"])
        coverage_pct = round(100 * len(covered) / total, 1) if total else 0.0

        return {
            "framework": payload.framework,
            "framework_label": framework["label"],
            "total_controls_evaluated": total,
            "covered": covered,
            "gaps": gaps,
            "coverage_pct": coverage_pct,
            "note": (
                "Evaluación heurística sobre un subconjunto de controles, basada solo "
                "en el texto aportado. No sustituye una auditoría formal de cumplimiento."
            ),
        }
