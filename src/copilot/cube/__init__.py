"""Q.93.C — Cube Fase 2: LLM nas bordas (interpreta NL → Cube REST → narra).

Camada que liga a pergunta livre em PT-PT ao Cube Core (Fase 1) sem deixar o
LLM tocar em SQL nem cálculo. Estrutura:

    client.py            — httpx wrapper do Cube REST API (/meta, /load)
    query.py             — Pydantic CubeQuery + validate_against_catalog
    material_retrieval.py — FAISS top-k sobre os ~1300 materiais distintos
    interpret.py         — NL → CubeQuery via structured_call (Pydantic)
    narrate.py           — payload → texto PT-PT + guard de números

Princípio: o Cube calcula; o LLM fala. Abdicação honesta em 3 pontos
(JSON inválido contra catálogo, resultado vazio, guard de narração).
"""
