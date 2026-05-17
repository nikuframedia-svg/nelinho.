"""Hashing de passwords — Q.31.G.

Login real por password (decisão D3 do Luis). Usa a biblioteca `bcrypt`
directamente — o `passlib` 1.7.4 não detecta o backend do `bcrypt` 4/5
(incompatibilidade conhecida), por isso falava-se com a API nativa.
"""

from __future__ import annotations

import bcrypt

# O bcrypt rejeita passwords com mais de 72 bytes — truncamos por baixo
# (prática-padrão) para nunca rebentar com uma password longa.
_MAX_BYTES = 72


def _encode(password: str) -> bytes:
    return password.encode("utf-8")[:_MAX_BYTES]


def hash_password(password: str) -> str:
    """Devolve o hash bcrypt de uma password em claro."""
    return bcrypt.hashpw(_encode(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Confirma se `plain` corresponde ao `hashed`.

    Um hash malformado/vazio devolve ``False`` (autenticação negada — o
    lado seguro) em vez de propagar a excepção.
    """
    if not plain or not hashed:
        return False
    try:
        return bcrypt.checkpw(_encode(plain), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False
