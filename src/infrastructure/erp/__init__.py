"""ERP integrations. Each subpackage is the ACL (anti-corruption layer)
for one concrete ERP product — it speaks the ERP's dialect on one side
and returns plain dicts / Pydantic DTOs on the other, so the rest of
ProdPlan ONE never learns what database vendor lives upstream.
"""
