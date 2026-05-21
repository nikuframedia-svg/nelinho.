"""Q.61.04 — roundtrip: backend ACTION_WIRING must equal frontend ACTION_WIRING.

CLAUDE.md (Q.17 secao "modifying YAML policy") diz:

    ACTION_WIRING matrix em `dispatchers.py` é mirrored no frontend
    `RegrasPage.tsx` `WIRED:` map. Quando flipares `wired=False→True`
    num lado, **flipar no outro também**.

O test existente em `tests/governance/test_yaml_engine_q17d.py:294`
(`test_action_wiring_matrix_has_entry_per_action_type`) so verifica
que o backend tem entrada por ActionType. NAO compara com o frontend.
Q.61.04 fecha esse buraco — parse do TS, compara keys + wired flags.
Se um lado ficar para tras, falha o CI.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.governance.yaml_policy.dispatchers import ACTION_WIRING as BACKEND_WIRING

FRONTEND_FILE = (
    Path(__file__).resolve().parents[2]
    / "frontend"
    / "src"
    / "components"
    / "regras"
    / "ruleHelpers.ts"
)


def _parse_frontend_wiring() -> dict[str, bool]:
    """Parse `ACTION_WIRING: Record<string, boolean> = { ... }` do TS.

    O bloco e estavel: cada linha tem `<key>: true,` ou `<key>: false,`
    (com comentarios de linha em // permitidos no fim). Nao precisamos
    de um parser TS completo — regex de uma linha cobre o formato actual
    e falha alto se alguem mudar a forma do bloco.
    """
    assert FRONTEND_FILE.exists(), (
        f"frontend ACTION_WIRING file not found at {FRONTEND_FILE}; "
        "Q.61.04 assumption broken — investigar antes de mexer"
    )
    source = FRONTEND_FILE.read_text(encoding="utf-8")

    # Localiza o bloco entre `ACTION_WIRING: ... = {` e o `};` correspondente.
    match = re.search(
        r"ACTION_WIRING\s*:\s*Record<string,\s*boolean>\s*=\s*\{(?P<body>[^}]+)\}",
        source,
        re.DOTALL,
    )
    if not match:
        raise AssertionError(
            "frontend ACTION_WIRING block not found in ruleHelpers.ts — "
            "alguem renomeou a constante ou mudou a forma. Investigar."
        )

    wiring: dict[str, bool] = {}
    for line in match.group("body").splitlines():
        # Remove trailing `// comment` antes de extrair.
        line = re.sub(r"//.*$", "", line).strip().rstrip(",").strip()
        if not line:
            continue
        # `key: true` ou `'key': false`.
        m = re.match(r"['\"]?(?P<key>[\w_]+)['\"]?\s*:\s*(?P<val>true|false)\s*$", line)
        if not m:
            raise AssertionError(
                f"frontend ACTION_WIRING line nao parseavel: {line!r}; "
                "regex de Q.61.04 ficou desactualizada — adiciona suporte ou simplifica o TS."
            )
        wiring[m.group("key")] = m.group("val") == "true"
    return wiring


def test_frontend_action_wiring_has_same_keys_as_backend():
    """Keys identicas dos dois lados — sem entradas orfas em nenhum."""
    frontend = _parse_frontend_wiring()
    backend_keys = set(BACKEND_WIRING.keys())
    frontend_keys = set(frontend.keys())

    missing_in_frontend = backend_keys - frontend_keys
    extra_in_frontend = frontend_keys - backend_keys

    assert not missing_in_frontend, (
        f"ACTION_WIRING dessincronizado — backend tem mas frontend nao: "
        f"{sorted(missing_in_frontend)}. Adicionar ao "
        f"frontend/src/components/regras/ruleHelpers.ts."
    )
    assert not extra_in_frontend, (
        f"ACTION_WIRING dessincronizado — frontend tem mas backend nao: "
        f"{sorted(extra_in_frontend)}. Remover do frontend ou adicionar "
        f"dispatcher em src/governance/yaml_policy/dispatchers.py."
    )


def test_frontend_action_wiring_flags_match_backend():
    """Para cada action, wired flag tem de ser igual nos dois lados.

    Quando se flipa wired=False→True no backend (porque o dispatcher
    ganhou wiring real), tem de se flipar no frontend tambem para que a
    UI deixe de mostrar o aviso "rule logs but doesn't enforce".
    """
    frontend = _parse_frontend_wiring()
    drift: list[str] = []
    for action, backend_entry in BACKEND_WIRING.items():
        backend_wired = bool(backend_entry.get("wired", False))
        frontend_wired = frontend.get(action)
        if frontend_wired is None:
            continue  # caught by the keys test
        if backend_wired != frontend_wired:
            drift.append(
                f"{action!r}: backend wired={backend_wired}, "
                f"frontend wired={frontend_wired}"
            )
    assert not drift, (
        "ACTION_WIRING wired flags drifted between backend and frontend:\n  "
        + "\n  ".join(drift)
        + "\nFlipar nos dois lados (dispatchers.py + ruleHelpers.ts)."
    )


def test_frontend_action_wiring_is_parseable():
    """Sanity meta-test: o nosso parser regex extrai pelo menos 1 entrada.

    Se alguem reescrever o ruleHelpers.ts e o bloco deixar de ser
    extraivel, queremos saber pelo nome do teste (nao via falha confusa
    dum dos testes acima).
    """
    frontend = _parse_frontend_wiring()
    assert len(frontend) >= 1, (
        "_parse_frontend_wiring devolveu mapa vazio — parser regex partido"
    )


if __name__ == "__main__":  # pragma: no cover - dev helper
    pytest.main([__file__, "-v"])
