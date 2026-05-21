"""ProdPlan ONE — supply services package.

Q.64.C — pacote introduzido para o `rop_calculator` recompute-from-ledger
ficar isolado do `src/supply/rop_calculator.py` original (stateless math).
"""

from src.supply.services.rop_calculator import recompute_rop_configs

__all__ = ["recompute_rop_configs"]
