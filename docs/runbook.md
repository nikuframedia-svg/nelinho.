# RUNBOOK — Operação e Qualidade (Sem Git)

## Comandos oficiais (canónicos)
- Diagnóstico do ambiente:
  - `./scripts/doctor.sh`
- Descoberta (mapa do repo):
  - `./scripts/discover.sh`
- Quality Gate local (antes de qualquer mudança):
  - `./scripts/check.sh`
- Operação Docker (prodplan-one):
  - `./scripts/up.sh`
  - `./scripts/smoke.sh`
  - `./scripts/down.sh`

## Mapa do sistema (auto-descoberto)
Este repositório contém sub-projetos aninhados (ex.: `prodplan-one/frontend`, `prodplan-one/backend`, `base-/backend`).
Usa `./scripts/discover.sh` para listar as localizações reais.

## Política anti-bugs (não negociável)
- Mudanças pequenas e verificáveis.
- Sem checks verdes (local), não se mexe em features.
- Não inventar scripts. Se faltarem `lint/typecheck/test/build`, registar e decidir conscientemente.

## Python — execução determinística (a implementar a seguir)
Objetivo: venv por projeto + instalação explícita + testes.
Exemplo (por pasta com requirements.txt):
1) `python3 -m venv .venv`
2) `source .venv/bin/activate`
3) `pip install -r requirements.txt`
4) `pytest` (se existir)

Nota: não executar automaticamente até definirmos o padrão por projeto.

## Desenvolvimento (workflow canónico)
- Backend (Docker):
  - `./scripts/dev-backend.sh`  (sobe stack + segue logs do api)
  - `./scripts/up.sh` / `./scripts/down.sh`
  - Smoke infra/logs: `./scripts/smoke.sh`
  - Smoke HTTP real: `./scripts/smoke-http.sh`

- Frontend (local):
  - `./scripts/dev-frontend.sh`

## Quality Gate (dia-a-dia)
- `./scripts/check.sh`  (lint reportado como DEBT, não bloqueia)
- `./scripts/check.sh --strict` (lint volta a bloquear)




