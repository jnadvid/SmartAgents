"""Herramientas de ciberseguridad defensiva.

- parse_wazuh_alert: normaliza alertas Wazuh (JSON) para análisis.
- map_to_mitre_attack: mapeo por palabras clave a técnicas MITRE ATT&CK
  (los identificadores de técnica son conocimiento público del framework).
- calculate_cvss_priority: prioridad operativa a partir de CVSS y contexto.
"""
from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field

from app.security.sanitization import normalize_for_matching
from app.tools.base import BaseTool, ToolContext, ToolError

# ---------------------------------------------------------------------------
# parse_wazuh_alert
# ---------------------------------------------------------------------------


class ParseWazuhAlertInput(BaseModel):
    alert: str = Field(min_length=2, max_length=100000, description="Alerta Wazuh en JSON")


def _severity_from_level(level: int | None) -> str:
    if level is None:
        return "unknown"
    if level >= 12:
        return "critical"
    if level >= 7:
        return "high"
    if level >= 4:
        return "medium"
    return "low"


class ParseWazuhAlertTool(BaseTool):
    name = "parse_wazuh_alert"
    category = "cybersecurity"
    description = (
        "Parsea una alerta Wazuh en JSON y extrae regla, nivel, agente, origen, "
        "campos MITRE y una severidad normalizada."
    )
    input_schema = ParseWazuhAlertInput
    timeout_seconds = 10

    def execute(self, payload: ParseWazuhAlertInput, ctx: ToolContext) -> dict[str, Any]:
        raw = payload.alert.strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ToolError(
                f"La alerta no es JSON válido (error en posición {exc.pos}). "
                "Pega la alerta completa de Wazuh en formato JSON."
            ) from exc
        if not isinstance(data, dict):
            raise ToolError("La alerta JSON debe ser un objeto, no una lista o escalar.")

        rule = data.get("rule") or {}
        agent = data.get("agent") or {}
        alert_data = data.get("data") or {}
        mitre = rule.get("mitre") or {}

        level_raw = rule.get("level")
        try:
            level = int(level_raw) if level_raw is not None else None
        except (TypeError, ValueError):
            level = None

        parsed = {
            "rule_id": rule.get("id"),
            "rule_level": level,
            "severity": _severity_from_level(level),
            "rule_description": rule.get("description"),
            "rule_groups": rule.get("groups") or [],
            "mitre_ids": mitre.get("id") or [],
            "mitre_tactics": mitre.get("tactic") or [],
            "mitre_techniques": mitre.get("technique") or [],
            "agent_name": agent.get("name"),
            "agent_id": agent.get("id"),
            "agent_ip": agent.get("ip"),
            "src_ip": alert_data.get("srcip") or alert_data.get("src_ip"),
            "src_user": alert_data.get("srcuser") or alert_data.get("dstuser"),
            "timestamp": data.get("timestamp"),
            "location": data.get("location"),
            "has_full_log": bool(data.get("full_log")),
            "fired_times": rule.get("firedtimes"),
        }
        missing = [key for key in ("rule_id", "rule_level", "rule_description") if parsed.get(key) in (None, "")]
        return {"parsed": parsed, "missing_fields": missing}


# ---------------------------------------------------------------------------
# map_to_mitre_attack
# ---------------------------------------------------------------------------

# Mapa reducido de técnicas MITRE ATT&CK (IDs públicos del framework) por
# palabras clave. Cobertura parcial a propósito: el agente debe declarar
# incertidumbre cuando no haya coincidencias.
_MITRE_MAP: list[dict[str, Any]] = [
    {"id": "T1110", "name": "Brute Force", "tactic": "Credential Access",
     "keywords": ["brute force", "fuerza bruta", "multiple failed login", "intentos fallidos", "password spraying", "authentication failure"]},
    {"id": "T1566", "name": "Phishing", "tactic": "Initial Access",
     "keywords": ["phishing", "spearphishing", "correo malicioso", "adjunto sospechoso", "enlace malicioso"]},
    {"id": "T1059", "name": "Command and Scripting Interpreter", "tactic": "Execution",
     "keywords": ["powershell", "cmd.exe", "bash -c", "script malicioso", "wscript", "cscript"]},
    {"id": "T1486", "name": "Data Encrypted for Impact", "tactic": "Impact",
     "keywords": ["ransomware", "cifrado de archivos", "files encrypted", "rescate", "extension .locked"]},
    {"id": "T1003", "name": "OS Credential Dumping", "tactic": "Credential Access",
     "keywords": ["mimikatz", "lsass", "credential dump", "volcado de credenciales", "sam database"]},
    {"id": "T1021", "name": "Remote Services", "tactic": "Lateral Movement",
     "keywords": ["rdp", "remote desktop", "ssh lateral", "smb lateral", "psexec", "winrm"]},
    {"id": "T1190", "name": "Exploit Public-Facing Application", "tactic": "Initial Access",
     "keywords": ["sql injection", "inyeccion sql", "web shell", "exploit publico", "log4j", "rce", "remote code execution"]},
    {"id": "T1078", "name": "Valid Accounts", "tactic": "Defense Evasion",
     "keywords": ["cuenta comprometida", "valid account", "login anomalo", "inicio de sesion inusual", "cuenta robada"]},
    {"id": "T1046", "name": "Network Service Discovery", "tactic": "Discovery",
     "keywords": ["port scan", "escaneo de puertos", "nmap", "network scan", "barrido de red"]},
    {"id": "T1041", "name": "Exfiltration Over C2 Channel", "tactic": "Exfiltration",
     "keywords": ["exfiltracion", "exfiltration", "data leak", "fuga de datos", "salida anomala de datos"]},
    {"id": "T1071", "name": "Application Layer Protocol", "tactic": "Command and Control",
     "keywords": ["c2", "command and control", "beacon", "dns tunneling", "trafico c2"]},
    {"id": "T1543", "name": "Create or Modify System Process", "tactic": "Persistence",
     "keywords": ["nuevo servicio", "service created", "persistencia", "systemd unit", "registro de inicio"]},
    {"id": "T1055", "name": "Process Injection", "tactic": "Defense Evasion",
     "keywords": ["process injection", "inyeccion de proceso", "dll injection", "hollowing"]},
    {"id": "T1098", "name": "Account Manipulation", "tactic": "Persistence",
     "keywords": ["usuario creado", "account created", "privilegios elevados", "added to administrators", "grupo admin"]},
    {"id": "T1562", "name": "Impair Defenses", "tactic": "Defense Evasion",
     "keywords": ["antivirus desactivado", "defender disabled", "logs borrados", "auditoria desactivada", "tamper"]},
]


class MapToMitreAttackInput(BaseModel):
    text: str = Field(min_length=3, max_length=100000, description="Descripción del evento o alerta")
    max_techniques: int = Field(default=5, ge=1, le=10)


class MapToMitreAttackTool(BaseTool):
    name = "map_to_mitre_attack"
    category = "cybersecurity"
    description = (
        "Sugiere técnicas MITRE ATT&CK candidatas por palabras clave a partir de "
        "la descripción de un evento. Cobertura parcial: úsalo como pista, no como verdad."
    )
    input_schema = MapToMitreAttackInput
    timeout_seconds = 10

    def execute(self, payload: MapToMitreAttackInput, ctx: ToolContext) -> dict[str, Any]:
        normalized = normalize_for_matching(payload.text)
        matches: list[dict[str, Any]] = []
        for technique in _MITRE_MAP:
            hits = [kw for kw in technique["keywords"] if kw in normalized]
            if hits:
                matches.append(
                    {
                        "technique_id": technique["id"],
                        "technique_name": technique["name"],
                        "tactic": technique["tactic"],
                        "matched_keywords": hits,
                        "confidence": "media" if len(hits) == 1 else "alta",
                    }
                )
        matches.sort(key=lambda m: -len(m["matched_keywords"]))
        return {
            "matches": matches[: payload.max_techniques],
            "match_count": len(matches),
            "note": (
                "Mapeo heurístico por palabras clave sobre un subconjunto del framework; "
                "verificar manualmente contra https://attack.mitre.org (consulta manual, la herramienta no navega)."
            ),
        }


# ---------------------------------------------------------------------------
# calculate_cvss_priority
# ---------------------------------------------------------------------------

_CVSS_IN_TEXT = re.compile(r"cvss[^0-9]{0,15}(\d{1,2}(?:[.,]\d))", re.IGNORECASE)

_CRITICALITY_FACTOR = {"low": 0.7, "medium": 1.0, "high": 1.25, "critical": 1.5}
_EXPOSURE_FACTOR = {"isolated": 0.7, "internal": 1.0, "internet": 1.35}


class CalculateCvssPriorityInput(BaseModel):
    cvss_score: float | None = Field(default=None, ge=0.0, le=10.0)
    text: str | None = Field(default=None, max_length=50000, description="Texto del que extraer el CVSS si no se pasa")
    asset_criticality: str = Field(default="medium", pattern="^(low|medium|high|critical)$")
    exposure: str = Field(default="internal", pattern="^(isolated|internal|internet)$")
    exploit_available: bool = False


class CalculateCvssPriorityTool(BaseTool):
    name = "calculate_cvss_priority"
    category = "cybersecurity"
    description = (
        "Calcula una prioridad operativa (P1-P4) y SLA sugerido a partir del CVSS "
        "base, criticidad del activo, exposición y disponibilidad de exploit."
    )
    input_schema = CalculateCvssPriorityInput
    timeout_seconds = 10

    def execute(self, payload: CalculateCvssPriorityInput, ctx: ToolContext) -> dict[str, Any]:
        cvss = payload.cvss_score
        extracted_from_text = False
        if cvss is None and payload.text:
            match = _CVSS_IN_TEXT.search(payload.text)
            if match:
                cvss = min(10.0, float(match.group(1).replace(",", ".")))
                extracted_from_text = True
        if cvss is None:
            raise ToolError(
                "No se proporcionó cvss_score ni se pudo extraer del texto. "
                "Indica la puntuación CVSS base (0.0-10.0)."
            )

        adjusted = cvss * _CRITICALITY_FACTOR[payload.asset_criticality] * _EXPOSURE_FACTOR[payload.exposure]
        if payload.exploit_available:
            adjusted *= 1.2
        adjusted = min(adjusted, 15.0)

        if adjusted >= 11.0:
            priority, sla = "P1", "24 horas"
        elif adjusted >= 8.0:
            priority, sla = "P2", "7 días"
        elif adjusted >= 5.0:
            priority, sla = "P3", "30 días"
        else:
            priority, sla = "P4", "90 días / próxima ventana"

        return {
            "cvss_base": cvss,
            "cvss_extracted_from_text": extracted_from_text,
            "asset_criticality": payload.asset_criticality,
            "exposure": payload.exposure,
            "exploit_available": payload.exploit_available,
            "adjusted_score": round(adjusted, 2),
            "priority": priority,
            "suggested_sla": sla,
            "rationale": (
                f"CVSS {cvss} x criticidad({payload.asset_criticality}) "
                f"x exposición({payload.exposure})"
                + (" x exploit disponible(1.2)" if payload.exploit_available else "")
            ),
        }
