<#
.SYNOPSIS
  Q.61.05 — Mutmut baseline para os modulos criticos do nelinho.

.DESCRIPTION
  Coverage alto pode esconder mutation score baixo (Anthropic post-mortem
  Abril 2026: 6 semanas de regressao silenciosa passaram coverage +
  unit + e2e). Mutmut force a suite a apanhar mutacoes semanticas — se
  um teste passa apos um operador != → ==, o teste e theater.

  Alvos:
    - src/plan/cpo/decoder.py +
      src/plan/cpo/fitness.py         Spelke axioms criticos (cura/secagem,
                                      mold exclusivo, capacity, precedence,
                                      safety_net baseline)
    - src/governance/yaml_policy/     write-gate + policy engine
    - src/shared/api/decisions.py     SoD + propose/approve flow

  Nota Q.66.C.3: o target `cpo` corre apenas decoder.py + fitness.py
  (Spelke-critical) e nao o modulo inteiro — `cpo/` completo demora
  >2h. Engine/scheduler/workforce ficam para targets dedicados futuros.

  Saida:
    - scripts/mutmut_baseline.json    snapshot estatistico
    - mutmut-cache/                   estado interno (gitignored)

.PARAMETER Module
  cpo | yaml_policy | decisions | all. Default: smoke (decisions sozinho,
  rapido — confirma que o setup esta sao sem correr todo o baseline).

.PARAMETER Pretend
  Mostra o que correria sem chamar mutmut. Util para review.

.EXAMPLE
  pwsh scripts/mutation_test.ps1
  pwsh scripts/mutation_test.ps1 -Module decisions
  pwsh scripts/mutation_test.ps1 -Module all
#>
[CmdletBinding()]
param(
    [ValidateSet("smoke", "cpo", "yaml_policy", "decisions", "all")]
    [string]$Module = "smoke",
    [switch]$Pretend
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot
$env:PYTHONPATH = "."
$env:PYTHONIOENCODING = "utf-8"  # Q.61.41 — mutmut imprime emoji 🎉; consola cp1252 crasha

$mutmut = Join-Path $repoRoot ".venv\Scripts\mutmut.exe"
if (-not (Test-Path $mutmut)) {
    Write-Host "mutmut nao instalado. Corre: .\.venv\Scripts\python.exe -m pip install -r requirements-test.txt" -ForegroundColor Red
    exit 2
}

$targets = @{
    smoke       = @{
        paths   = "src/shared/api/decisions.py"
        tests   = "tests/shared/test_decisions_advisory.py tests/shared/test_auth_rbac.py"
        timeout = 120
    }
    decisions   = @{
        paths   = "src/shared/api/decisions.py"
        tests   = "tests/shared/test_decisions_advisory.py tests/shared/test_auth_rbac.py"
        timeout = 600
    }
    yaml_policy = @{
        paths   = "src/governance/yaml_policy/"
        tests   = "tests/governance/"
        timeout = 1800
    }
    cpo         = @{
        # Q.66.C.3: scope reduzido a decoder.py + fitness.py — sao os
        # ficheiros onde vivem os 7 Spelke axioms (cura/secagem 16
        # transicoes, mold exclusivo, capacity, precedence, safety_net
        # baseline). cpo/ inteiro tem GA/scheduler/workforce — esses
        # ganham targets dedicados se quisermos cobertura adicional.
        paths   = "src/plan/cpo/decoder.py,src/plan/cpo/fitness.py"
        tests   = "tests/plan/test_cpo_decoder.py tests/plan/test_decoder_p0_fixes.py tests/plan/test_fitness_quality_risk.py tests/plan/test_axiom3_mold_exclusivity_q13e.py tests/plan/test_safety_net_axiom_7.py tests/plan/test_curing_constraints.py"
        timeout = 1800
    }
}

if ($Module -eq "all") {
    $order = @("decisions", "yaml_policy", "cpo")
}
else {
    $order = @($Module)
}

$baseline = @{
    started_at = (Get-Date).ToUniversalTime().ToString("o")
    runs       = @()
}

foreach ($m in $order) {
    $t = $targets[$m]
    Write-Host "" -ForegroundColor White
    Write-Host "[$m] paths=$($t.paths)  tests=$($t.tests)  timeout=$($t.timeout)s" -ForegroundColor Cyan

    # Q.61.41 — subprocess do mutmut nao herda venv activation; chamamos
    # pytest via `python -m pytest` com path absoluto ao interpreter.
    $py = Join-Path $repoRoot ".venv\Scripts\python.exe"
    $runnerArgs = @(
        "run",
        "--paths-to-mutate", $t.paths,
        "--runner", "$py -m pytest -x --tb=no -q $($t.tests)",
        "--tests-dir", "tests/"
    )

    if ($Pretend) {
        Write-Host "  (pretend) & $mutmut $runnerArgs" -ForegroundColor Yellow
        continue
    }

    # Q.66.C.3: mutmut grava .mutmut-cache no repo root (single sqlite).
    # Se nao limparmos entre targets, o `results` mistura sobreviventes
    # do target anterior.
    $cachePath = Join-Path $repoRoot ".mutmut-cache"
    if (Test-Path $cachePath) {
        Remove-Item $cachePath -Force
        Write-Host "  cleared .mutmut-cache (clean baseline para $m)" -ForegroundColor DarkGray
    }

    $start = Get-Date
    & $mutmut @runnerArgs
    $exit = $LASTEXITCODE
    $elapsed = (Get-Date) - $start

    # mutmut exits non-zero quando ha survivors — isto e o ponto, nao
    # falha do script. Capturamos o resumo para o baseline.
    $resultsOut = & $mutmut "results"
    $resultsText = ($resultsOut | Out-String).Trim()

    $baseline.runs += @{
        module       = $m
        paths        = $t.paths
        tests        = $t.tests
        exit_code    = $exit
        elapsed_secs = [math]::Round($elapsed.TotalSeconds, 1)
        results      = $resultsText
    }

    Write-Host "  exit=$exit elapsed=$([math]::Round($elapsed.TotalSeconds, 1))s" -ForegroundColor Green
}

if (-not $Pretend) {
    $baselinePath = Join-Path $repoRoot "scripts\mutmut_baseline.json"
    $baseline | ConvertTo-Json -Depth 5 | Out-File -FilePath $baselinePath -Encoding utf8
    Write-Host "" -ForegroundColor White
    Write-Host "Baseline gravado em $baselinePath" -ForegroundColor Green
}
