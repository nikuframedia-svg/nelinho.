"""Q.66.D.4a — dependencies partilhadas pelos sub-routers do copilot.

`get_tenant_id` e `dev_only` viviam em `src/copilot/api.py` e eram
usadas em múltiplos endpoints. Centralizar aqui evita duplicação e
mantém o `api.py` agregador como um simples wire-up de sub-routers.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import Header, HTTPException, status

from src.shared.config import settings
from src.shared.auth.headers import require_tenant_header


get_tenant_id = require_tenant_header


# Q.168.D — dev_only promovido para src/shared/auth/headers.py (o gate é
# transversal: profit/copilot/...). Re-export mantém todos os imports
# existentes (`_common.dev_only` / `_api.dev_only`) a funcionar.
from src.shared.auth.headers import dev_only
