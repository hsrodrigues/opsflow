"""Background jobs — the "robôs" that keep the system's state honest without
a human having to open a screen and notice (seção 41 "Automações", V2 no
roadmap original, adiantado por já ter infraestrutura pronta e valor claro:
detecção automática de atraso, alerta de CNH vencendo, expiração de
licença). Each job is a plain function (`run()`) that opens its own DB
session and sweeps every active tenant — see `app/jobs/scheduler.py` for how
they're scheduled, and `docs/ARCHITECTURE.md` for the design rationale.
"""
