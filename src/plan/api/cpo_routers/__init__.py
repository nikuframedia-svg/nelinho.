"""Q.67.6.B2 — sub-routers do CPO API (decomposição de god-file 1104L).

Cada módulo declara o próprio APIRouter sem prefix (paths relativos a
`/v1/plan/cpo`, fornecido pelo agregador em `src/plan/api/cpo.py`).
"""
