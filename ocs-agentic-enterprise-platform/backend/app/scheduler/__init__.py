"""Programador de tareas local (sin dependencias externas).

Calcula próximas ejecuciones y dispara tareas (a un agente, un equipo o en
modo auto) de forma puntual o periódica, usando un hilo en segundo plano y
SQLite como única fuente de verdad. Sin Celery, sin Redis, sin cron del SO.
"""
