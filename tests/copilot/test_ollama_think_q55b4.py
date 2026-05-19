"""
Q.55.B.4 — `OllamaClient.chat` desliga o thinking do gemma4:e4b.

`gemma4:e4b` é um modelo de raciocínio: sem `think:false` emite o raciocínio
num campo `thinking` separado e o `content` pode vir vazio quando o raciocínio
esgota o `num_predict`. O `chat` fazia `json.loads(content)` às cegas →
`json.loads("")` lança o críptico "Expecting value: line 1 column 1".
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.copilot.ollama_client import OllamaClient


def _fake_client(response_data: dict) -> Mock:
    """Cliente httpx falso cujo `.post` devolve `response_data` como JSON."""
    resp = Mock()
    resp.raise_for_status = Mock()
    resp.json = Mock(return_value=response_data)
    client = Mock()
    client.post = AsyncMock(return_value=resp)
    return client


@pytest.mark.asyncio
async def test_payload_inclui_think_false():
    """O pedido /api/chat leva `think: false` — o modelo não desperdiça o
    orçamento de tokens em raciocínio que depois é descartado."""
    client = OllamaClient(max_retries=0)
    fake = _fake_client({"message": {"content": '{"summary": "ok"}'}})
    with patch.object(client, "_get_client", AsyncMock(return_value=fake)):
        await client.chat("pergunta", "gemma4:e4b", format="json")

    sent = fake.post.call_args.kwargs["json"]
    assert sent["think"] is False


@pytest.mark.asyncio
async def test_content_vazio_da_erro_claro():
    """content vazio (raciocínio comeu o orçamento) + format=json → erro
    legível, não o críptico 'Expecting value: line 1 column 1'."""
    client = OllamaClient(max_retries=0)
    fake = _fake_client({"message": {"content": "", "thinking": ""}})
    with patch.object(client, "_get_client", AsyncMock(return_value=fake)):
        with pytest.raises(Exception) as exc:
            await client.chat("pergunta", "gemma4:e4b", format="json")

    msg = str(exc.value)
    assert "vazia" in msg
    assert "Expecting value" not in msg


@pytest.mark.asyncio
async def test_json_valido_continua_a_devolver_dict():
    """Caminho feliz: content com JSON válido devolve o dict parseado."""
    client = OllamaClient(max_retries=0)
    fake = _fake_client(
        {"message": {"content": '{"summary": "gargalo na Laminagem"}'}}
    )
    with patch.object(client, "_get_client", AsyncMock(return_value=fake)):
        out = await client.chat("pergunta", "gemma4:e4b", format="json")

    assert out == {"summary": "gargalo na Laminagem"}
