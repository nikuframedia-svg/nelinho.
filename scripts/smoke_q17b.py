"""Q.17.B smoke test — exercise rule_schema + llm_tools + loader."""
from pathlib import Path

from src.governance.yaml_policy import (
    ActionType,
    EventType,
    Rule,
    TenantRulesYaml,
    load_tenant_rules,
    propose_rule_tool,
)
from src.governance.yaml_policy.loader import _read_yaml


def main() -> None:
    yaml_dir = Path("config/yaml")

    # 1) tenant_rules.yaml does not exist yet → empty doc
    doc = load_tenant_rules(yaml_dir)
    print(f"empty doc: version={doc.version} rules={len(doc.rules)}")

    # 2) Load the example file
    raw = _read_yaml(yaml_dir / "tenant_rules.example.yaml")
    example = TenantRulesYaml.model_validate(raw)
    print(f"example: version={example.version} rules={[r.id for r in example.rules]}")

    # 3) Show enum coverage
    print(f"events ({len(EventType)}): {[e.value for e in EventType]}")
    print(f"actions ({len(ActionType)}): {[a.value for a in ActionType]}")

    # 4) Inspect tool spec
    spec = propose_rule_tool()
    fn = spec["function"]
    params = fn["parameters"]
    print(f"tool: {fn['name']}, top-level fields: {list(params['properties'].keys())}")
    print(
        "tool event enum size:",
        len(params["properties"]["when"]["properties"]["event"]["enum"]),
    )
    print(
        "tool action enum size:",
        len(params["properties"]["then"]["items"]["properties"]["action"]["enum"]),
    )

    # 5) Round-trip: build a Rule programmatically
    r = Rule.model_validate(example.rules[0].model_dump())
    print(f"round-trip rule {r.id}: status={r.status.value} axioms={[a.value for a in r.constraints.axioms_required]}")

    print("OK")


if __name__ == "__main__":
    main()
