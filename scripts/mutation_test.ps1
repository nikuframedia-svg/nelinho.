<#
.SYNOPSIS
  Q.61.05 — Mutmut baseline para os modulos criticos do nelinho.

.DESCRIPTION
  Coverage alto pode esconder mutation score baixo (Anthropic post-mortem
  Abril 2026: 6 semanas de regressao silenciosa passaram coverage +
  unit + e2e). Mutmut force a suite a apanhar mutacoes semanticas — se
  um teste passa apos um operador != → ==, o teste e theater.

  Alvos:
    - src/plan/cpo/                   nucleo Spelke + GA + decoder
    - src/governance/yaml_policy/     write-gate + policy engine
    - src/shared/api/decisions.py     SoD + propose/approve flow

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
        paths   = "src/plan/cpo/"
        tests   = "tests/plan/"
        timeout = 3600
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

    $runnerArgs = @(
        "run",
        "--paths-to-mutate", $t.paths,
        "--runner", "pytest -x --tb=no -q $($t.tests)",
        "--tests-dir", "tests/"
    )

    if ($Pretend) {
        Write-Host "  (pretend) & $mutmut $runnerArgs" -ForegroundColor Yellow
        continue
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
