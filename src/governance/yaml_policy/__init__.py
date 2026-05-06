"""YAML policy module — Sprint Q.17 logic-as-data.

Single source of truth for system-level configuration AND declarative
business rules.

- Q.17.A foundation: ``system_defaults.yaml`` + loader (this module).
- Q.17.B DSL + LLM tools: ``tenant_rules.yaml`` schema + function-calling
  specs for NL→YAML rule authoring.
- Q.17.C frontend ``/regras`` page (separate sprint).
- Q.17.D engine + dispatchers (separate sprint).
- Q.17.E safety mechanisms (separate sprint).
"""

from .condition_evaluator import evaluate_all, evaluate_condition
from .dispatchers import (
    DispatchContext,
    DispatchResult,
    dispatch,
)
from .engine import RuleEngine
from .safety_checks import (
    AxiomChecker,
    ConflictResolver,
    RuleSafetyError,
    SafetyViolation,
    run_safety_checks,
)
from .llm_tools import (
    propose_rule_tool,
    propose_rule_tool_json,
    rule_to_yaml_dict,
)
from .loader import (
    DEFAULT_YAML_DIR,
    YamlPolicyError,
    load_seeds,
    load_system_defaults,
    load_tenant_rules,
    system_defaults_to_seeds,
)
from .rule_schema import (
    ACTION_PARAMS,
    EVENT_FIELDS,
    ActionStep,
    ActionType,
    AxiomRequirement,
    Condition,
    ConditionOp,
    ConstraintsSpec,
    EventType,
    Rule,
    RuleStatus,
    SafetySpec,
    TenantRulesYaml,
    TriggerSpec,
)
from .schema import (
    CategoryDef,
    SettingDataType,
    SettingDef,
    SystemDefaultsYaml,
)

__all__ = [
    # Q.17.A — system defaults
    "CategoryDef",
    "DEFAULT_YAML_DIR",
    "SettingDataType",
    "SettingDef",
    "SystemDefaultsYaml",
    "YamlPolicyError",
    "load_seeds",
    "load_system_defaults",
    "system_defaults_to_seeds",
    # Q.17.B — tenant rules schema
    "ACTION_PARAMS",
    "EVENT_FIELDS",
    "ActionStep",
    "ActionType",
    "AxiomRequirement",
    "Condition",
    "ConditionOp",
    "ConstraintsSpec",
    "EventType",
    "Rule",
    "RuleStatus",
    "SafetySpec",
    "TenantRulesYaml",
    "TriggerSpec",
    "load_tenant_rules",
    # Q.17.B — LLM function-calling
    "propose_rule_tool",
    "propose_rule_tool_json",
    "rule_to_yaml_dict",
    # Q.17.D — runtime engine + dispatchers
    "DispatchContext",
    "DispatchResult",
    "RuleEngine",
    "dispatch",
    "evaluate_all",
    "evaluate_condition",
    # Q.17.E — pre-approval safety
    "AxiomChecker",
    "ConflictResolver",
    "RuleSafetyError",
    "SafetyViolation",
    "run_safety_checks",
]
