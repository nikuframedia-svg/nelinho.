"""Q.117.E/F — verificação LIVE das vertentes LLM contra o Ollama real.

Corre contra o Ollama on-prem (gemma4:e4b, think:false). NÃO precisa do
uvicorn nem do ERP — exercita os pipelines reais directamente:

  E (copiloto): intent router + uma chamada real ao modelo (confirma que
     o gemma4:e4b responde com think:false, conteúdo não vazio).
  F (rule-author): translate_nl_to_rule (NL PT-PT → Rule estruturada) e
     confirma o invariante requires_human_approval == True.

Uso:
    .\.venv\Scripts\python.exe scripts/q117_llm_live_verify.py
"""
from __future__ import annotations

import asyncio
import sys


async def verify_copilot() -> bool:
    print("\n=== E · COPILOTO (intent router + LLM live) ===")
    ok = True
    try:
        from src.copilot.intent_router import detect_intent

        samples = {
            "qual é o OEE hoje?": "kpi_current",
            "porque caiu a qualidade na laminagem?": "diagnostic",
            "resumo de qualidade desta semana": "quality_summary",
        }
        for q, _expected in samples.items():
            intent = detect_intent(q)
            print(f"  intent({q!r}) -> {intent}")
    except Exception as exc:
        print(f"  FAIL intent router: {type(exc).__name__}: {exc}")
        ok = False

    try:
        from src.copilot.ollama_client import OllamaClient
        from src.shared.config import settings

        client = OllamaClient()
        model = getattr(settings, "ollama_model", "gemma4:e4b")
        # chat(format="json") devolve o JSON JÁ parseado (dict), não {"content":...}.
        resp = await client.chat(
            prompt=(
                "Responde APENAS em JSON com a forma exacta "
                '{"resumo": "<uma frase curta em PT-PT>"}. '
                "Pergunta: quantas ordens estão em curso?"
            ),
            model=model,
            format="json",
        )
        print(f"  ollama model={model} think={getattr(settings,'ollama_think',None)}")
        print(f"  resp={str(resp)[:200]!r}")
        if not (isinstance(resp, dict) and resp):
            print("  FAIL: resposta JSON vazia/ inválida")
            ok = False
        else:
            print("  OK: modelo respondeu JSON estruturado não-vazio")
    except Exception as exc:
        print(f"  FAIL chamada Ollama: {type(exc).__name__}: {exc}")
        ok = False
    return ok


async def verify_rule_author() -> bool:
    print("\n=== F · RULE-AUTHOR (NL PT-PT -> Rule estruturada) ===")
    try:
        from src.governance.yaml_policy.nl_translator import translate_nl_to_rule

        nl = (
            "Quando um molde atingir 1000 usos, propor manutenção preventiva "
            "e alertar o responsável de produção."
        )
        rule = await translate_nl_to_rule(nl)
        event = getattr(rule, "event", None)
        actions = [getattr(a, "type", a) for a in getattr(rule, "then", []) or []]
        rha = rule.safety.requires_human_approval
        print(f"  event={event}")
        print(f"  actions={actions}")
        print(f"  requires_human_approval={rha}")
        if rha is not True:
            print("  FAIL: requires_human_approval tem de ser True (invariante Q.17)")
            return False
        return True
    except Exception as exc:
        print(f"  FAIL rule-author: {type(exc).__name__}: {exc}")
        return False


async def main() -> int:
    e_ok = await verify_copilot()
    f_ok = await verify_rule_author()
    print("\n=== RESUMO ===")
    print(f"  E copiloto:    {'OK' if e_ok else 'FALHOU'}")
    print(f"  F rule-author: {'OK' if f_ok else 'FALHOU'}")
    return 0 if (e_ok and f_ok) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
