# Runbook: OllamaDown

**Alert:** `OllamaDown` for 5 min. **Severity:** warning.

## Blast radius

Copilot free-form answers degrade (rule-based fallback still works
via guardrails). CausalChain validator can still run rule-based
layers but the "LLM-generated chain" path returns a notice instead
of a real answer. **No hard outage.**

## Diagnose

```bash
systemctl status ollama
journalctl -u ollama --since "15 min ago" -n 200
curl -sf http://localhost:11434/api/tags
nvidia-smi   # GPU OOM is common with the 7B model
```

## Mitigate

1. **Restart**: `systemctl restart ollama`.
2. **GPU OOM**: switch to the lighter model via tenant config, then
   pull it:
   ```bash
   ollama pull gemma3:4b
   ```
3. **Model corruption**: `ollama rm <model>; ollama pull <model>`.

## Verify

`curl http://localhost:11434/api/tags` returns JSON with at least the
default model. The Copilot response pathway stops returning the
"LLM unavailable" notice.
