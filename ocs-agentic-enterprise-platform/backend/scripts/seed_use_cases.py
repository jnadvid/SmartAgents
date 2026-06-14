"""Crea casos de uso de ejemplo (conector Wazuh + tareas programadas).

Uso:
    python backend/scripts/seed_use_cases.py            # crea las tareas PAUSADAS
    python backend/scripts/seed_use_cases.py --activate  # crea las tareas activas

Copia examples/wazuh_alerts.sample.json al archivo que lee el conector
(backend/data/connectors/wazuh/alerts.json) y registra tareas programadas que
ilustran la automatización (p. ej. el bucle del SOC). Es idempotente: omite las
tareas cuyo nombre ya exista.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import PROJECT_ROOT, get_settings
from app.database import SessionLocal, init_db
from app.schemas import ScheduledTaskCreate
from app.services import scheduler_service
from app.services.agent_runner import get_agent_registry, get_squad_registry

# Casos de uso de ejemplo (uno por patrón). Más en docs/use_cases.md.
EXAMPLES: list[dict] = [
    {
        "name": "SOC · Investigación de alertas Wazuh",
        "task": (
            "Investiga las alertas de seguridad recibidas, prioriza, descarta falsos "
            "positivos y DECIDE la derivación y la conclusión final."
        ),
        "target_kind": "squad", "target_ref": "soc_investigation_team",
        "connector": "wazuh_alerts", "connector_params": {"min_level": 7, "limit": 50},
        "schedule_kind": "interval", "interval_minutes": 30,
    },
    {
        "name": "Threat hunting diario",
        "task": "Formula hipótesis de caza sobre las alertas recientes y propón detecciones.",
        "target_kind": "agent", "target_ref": "threat_hunter",
        "connector": "wazuh_alerts", "connector_params": {"min_level": 5, "limit": 100},
        "schedule_kind": "daily", "time_of_day": "07:30", "timezone": "Europe/Madrid",
    },
    {
        "name": "Ingeniería de detección semanal",
        "task": "Propón una regla Sigma nueva para una técnica MITRE no cubierta esta semana.",
        "target_kind": "agent", "target_ref": "detection_engineer",
        "schedule_kind": "weekly", "day_of_week": 0, "time_of_day": "09:00", "timezone": "Europe/Madrid",
    },
    {
        "name": "Concienciación en seguridad (mensual)",
        "task": "Diseña la campaña de concienciación del mes y su material formativo.",
        "target_kind": "squad", "target_ref": "security_awareness_team",
        "schedule_kind": "cron", "cron": "0 9 1 * *", "timezone": "Europe/Madrid",
    },
]


def copy_sample_alerts() -> Path:
    settings = get_settings()
    dest = settings.connectors_dir / "wazuh" / "alerts.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    sample = PROJECT_ROOT / "examples" / "wazuh_alerts.sample.json"
    if sample.exists():
        shutil.copyfile(sample, dest)
    return dest


def main(activate: bool) -> None:
    init_db()
    dest = copy_sample_alerts()
    print(f"Alertas de ejemplo en: {dest}")

    agent_registry = get_agent_registry()
    squad_names = set(get_squad_registry().names())
    created, skipped = 0, 0
    with SessionLocal() as db:
        existing = {t.name for t in scheduler_service.list_tasks(db)}
        for example in EXAMPLES:
            if example["name"] in existing:
                skipped += 1
                continue
            task = scheduler_service.create_task(
                db, ScheduledTaskCreate(**example),
                agent_registry=agent_registry, squad_names=squad_names,
            )
            if not activate:
                scheduler_service.set_enabled(db, task, False)
            created += 1
            state = "activa" if activate else "pausada"
            print(f"  + [{state}] {task.name}  ({task.schedule_kind})")

    print(f"\nHecho. Creadas: {created}, ya existentes: {skipped}.")
    if not activate:
        print("Las tareas están PAUSADAS. Actívalas desde la pestaña Programador o re-ejecuta con --activate.")


if __name__ == "__main__":
    main(activate="--activate" in sys.argv)
