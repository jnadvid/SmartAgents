"""Cálculo de próximas ejecuciones para tareas programadas.

Funciones puras (sin base de datos) sobre una especificación `ScheduleSpec`,
para que sean fáciles de probar de forma determinista. Todas las marcas de
tiempo de entrada y salida están en UTC y son *aware*.

Tipos de programación soportados:
- once:     una sola vez en `run_at`.
- interval: cada `interval_minutes` minutos.
- daily:    todos los días a las `time_of_day` (HH:MM) en `timezone`.
- weekly:   cada semana en `day_of_week` (0=lunes … 6=domingo) a `time_of_day`.
- cron:     expresión cron de 5 campos (min hora dom mes dow; dow 0/7=domingo).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SCHEDULE_KINDS = ("once", "interval", "daily", "weekly", "cron")
_CRON_SEARCH_LIMIT_MINUTES = 367 * 24 * 60  # ~1 año, cota de seguridad


@dataclass(frozen=True)
class ScheduleSpec:
    """Especificación de programación independiente de la base de datos."""

    kind: str
    run_at: datetime | None = None
    interval_minutes: int | None = None
    time_of_day: str | None = None
    day_of_week: int | None = None
    cron: str | None = None
    timezone: str = "UTC"


class ScheduleError(ValueError):
    """Especificación de programación inválida."""


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def _ensure_utc(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except (ZoneInfoNotFoundError, ValueError, KeyError) as exc:
        raise ScheduleError(f"Zona horaria desconocida: '{name}'.") from exc


def parse_time_of_day(value: str | None) -> tuple[int, int]:
    """Convierte 'HH:MM' en (hora, minuto) validando el rango."""
    if not value:
        raise ScheduleError("Se requiere la hora del día en formato HH:MM.")
    parts = value.strip().split(":")
    if len(parts) != 2:
        raise ScheduleError(f"Hora inválida: '{value}'. Usa el formato HH:MM.")
    try:
        hour, minute = int(parts[0]), int(parts[1])
    except ValueError as exc:
        raise ScheduleError(f"Hora inválida: '{value}'. Usa el formato HH:MM.") from exc
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ScheduleError(f"Hora fuera de rango: '{value}'.")
    return hour, minute


def validate_spec(spec: ScheduleSpec) -> None:
    """Valida la especificación. Lanza ScheduleError si es inconsistente."""
    if spec.kind not in SCHEDULE_KINDS:
        raise ScheduleError(f"Tipo de programación no soportado: '{spec.kind}'.")
    _zone(spec.timezone)
    if spec.kind == "once":
        if spec.run_at is None:
            raise ScheduleError("La programación 'once' requiere 'run_at'.")
    elif spec.kind == "interval":
        if not spec.interval_minutes or spec.interval_minutes < 1:
            raise ScheduleError("La programación 'interval' requiere 'interval_minutes' >= 1.")
    elif spec.kind == "daily":
        parse_time_of_day(spec.time_of_day)
    elif spec.kind == "weekly":
        parse_time_of_day(spec.time_of_day)
        if spec.day_of_week is None or not (0 <= spec.day_of_week <= 6):
            raise ScheduleError("La programación 'weekly' requiere 'day_of_week' entre 0 (lunes) y 6 (domingo).")
    elif spec.kind == "cron":
        _parse_cron(spec.cron)  # valida la expresión


# ---------------------------------------------------------------------------
# Cálculo de próximas ejecuciones
# ---------------------------------------------------------------------------


def first_run_at(spec: ScheduleSpec, now: datetime) -> datetime | None:
    """Primera ejecución a partir de `now` (al crear la tarea)."""
    now = _ensure_utc(now)
    if spec.kind == "once":
        run_at = _ensure_utc(spec.run_at) if spec.run_at else None
        if run_at is None:
            return None
        return max(run_at, now)  # si está en el pasado, se ejecuta cuanto antes
    if spec.kind == "interval":
        return now  # arranca de inmediato; luego cada interval_minutes
    return next_run_at_after(spec, now - timedelta(minutes=1))


def next_run_at_after(spec: ScheduleSpec, after: datetime) -> datetime | None:
    """Siguiente ejecución estrictamente posterior a `after` (UTC)."""
    after = _ensure_utc(after)
    if spec.kind == "once":
        return None  # no se repite
    if spec.kind == "interval":
        minutes = spec.interval_minutes or 1
        return after + timedelta(minutes=minutes)
    if spec.kind == "daily":
        return _next_daily(spec, after)
    if spec.kind == "weekly":
        return _next_weekly(spec, after)
    if spec.kind == "cron":
        return _next_cron(spec, after)
    raise ScheduleError(f"Tipo de programación no soportado: '{spec.kind}'.")


def _next_daily(spec: ScheduleSpec, after: datetime) -> datetime:
    hour, minute = parse_time_of_day(spec.time_of_day)
    zone = _zone(spec.timezone)
    local_after = after.astimezone(zone)
    candidate = local_after.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= local_after:
        candidate += timedelta(days=1)
    return candidate.astimezone(timezone.utc)


def _next_weekly(spec: ScheduleSpec, after: datetime) -> datetime:
    hour, minute = parse_time_of_day(spec.time_of_day)
    zone = _zone(spec.timezone)
    target_dow = int(spec.day_of_week or 0)  # 0=lunes (Python weekday)
    local_after = after.astimezone(zone)
    candidate = local_after.replace(hour=hour, minute=minute, second=0, microsecond=0)
    days_ahead = (target_dow - candidate.weekday()) % 7
    candidate += timedelta(days=days_ahead)
    if candidate <= local_after:
        candidate += timedelta(days=7)
    return candidate.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Cron (5 campos: minuto hora día-mes mes día-semana)
# ---------------------------------------------------------------------------


def _parse_field(field: str, low: int, high: int) -> set[int]:
    values: set[int] = set()
    for part in field.split(","):
        part = part.strip()
        step = 1
        if "/" in part:
            base, step_str = part.split("/", 1)
            step = int(step_str)
            if step < 1:
                raise ScheduleError(f"Paso inválido en cron: '{part}'.")
        else:
            base = part
        if base in ("*", ""):
            start, end = low, high
        elif "-" in base:
            start_str, end_str = base.split("-", 1)
            start, end = int(start_str), int(end_str)
        else:
            start = end = int(base)
        if start < low or end > high or start > end:
            raise ScheduleError(f"Valor fuera de rango en cron: '{part}' (esperado {low}-{high}).")
        values.update(range(start, end + 1, step))
    return values


def _parse_cron(expression: str | None) -> dict[str, set[int]]:
    if not expression or not expression.strip():
        raise ScheduleError("La programación 'cron' requiere una expresión.")
    fields = expression.split()
    if len(fields) != 5:
        raise ScheduleError(
            "La expresión cron debe tener 5 campos: 'minuto hora día-mes mes día-semana'."
        )
    minute, hour, dom, month, dow = fields
    dow_values = _parse_field(dow, 0, 7)
    if 7 in dow_values:  # 0 y 7 representan domingo en cron
        dow_values.discard(7)
        dow_values.add(0)
    return {
        "minute": _parse_field(minute, 0, 59),
        "hour": _parse_field(hour, 0, 23),
        "dom": _parse_field(dom, 1, 31),
        "month": _parse_field(month, 1, 12),
        "dow": dow_values,
        "_dom_restricted": set() if dom.strip() == "*" else {1},
        "_dow_restricted": set() if dow.strip() == "*" else {1},
    }


def _cron_matches(fields: dict[str, set[int]], moment: datetime) -> bool:
    if moment.minute not in fields["minute"]:
        return False
    if moment.hour not in fields["hour"]:
        return False
    if moment.month not in fields["month"]:
        return False
    # En cron, día-del-mes 0=domingo: Python weekday lunes=0 -> convertir.
    cron_dow = (moment.weekday() + 1) % 7  # lunes=1 … domingo=0
    dom_ok = moment.day in fields["dom"]
    dow_ok = cron_dow in fields["dow"]
    dom_restricted = bool(fields["_dom_restricted"])
    dow_restricted = bool(fields["_dow_restricted"])
    if dom_restricted and dow_restricted:
        return dom_ok or dow_ok  # semántica OR de crontab
    return dom_ok and dow_ok


def _next_cron(spec: ScheduleSpec, after: datetime) -> datetime | None:
    fields = _parse_cron(spec.cron)
    zone = _zone(spec.timezone)
    local = after.astimezone(zone).replace(second=0, microsecond=0) + timedelta(minutes=1)
    for _ in range(_CRON_SEARCH_LIMIT_MINUTES):
        if _cron_matches(fields, local):
            return local.astimezone(timezone.utc)
        local += timedelta(minutes=1)
    return None


# ---------------------------------------------------------------------------
# Descripción legible
# ---------------------------------------------------------------------------

_WEEKDAYS_ES = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


def describe_schedule(spec: ScheduleSpec) -> str:
    """Texto legible de la programación (para UI/logs)."""
    if spec.kind == "once":
        return f"Una vez el {spec.run_at:%Y-%m-%d %H:%M UTC}" if spec.run_at else "Una vez"
    if spec.kind == "interval":
        return f"Cada {spec.interval_minutes} minuto(s)"
    if spec.kind == "daily":
        return f"Cada día a las {spec.time_of_day} ({spec.timezone})"
    if spec.kind == "weekly":
        day = _WEEKDAYS_ES[int(spec.day_of_week or 0)]
        return f"Cada {day} a las {spec.time_of_day} ({spec.timezone})"
    if spec.kind == "cron":
        return f"Cron '{spec.cron}' ({spec.timezone})"
    return spec.kind
