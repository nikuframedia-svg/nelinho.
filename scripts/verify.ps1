<#
.SYNOPSIS
  Q.61.39 — gate completo do nelinho num comando.

.DESCRIPTION
  Anthropic best-practices ("tight loop > full suite") + Karpathy
  ("verification speed > generation speed"): manter um caminho rapido
  ANTES de cada commit. Este script junta tudo o que o CI corre
  (alembic check excluido — precisa de Postgres a correr):

    1. ruff check src/
    2. pytest tests/governance + tests/shared (canary)
    3. python scripts/verify_invariants.py
    4. python scripts/lint_drift_gate.py
    5. cd frontend; npx tsc -b --noEmit
    6. cd frontend; npm test -- --run
    7. cd frontend; npm run lint:mocks

  Tempo total esperado: ~70-90s no laptop. Pre-commit ja corre 1+3+5+
  6+7 dos files tocados; este script e o "full verify" antes de push.

.PARAMETER QuickPython
  Salta tests/shared + tests/governance — mais rapido para iteracoes
  intermedias. Default: false (corre tudo).

.PARAMETER SkipFrontend
  Salta os 3 steps do frontend (uso debug-only quando se mexe so
  no backend).

.EXAMPLE
  pwsh scripts/verify.ps1
  pwsh scripts/verify.ps1 -QuickPython
  pwsh scripts/verify.ps1 -SkipFrontend
#>
[CmdletBinding()]
param(
    [switch]$QuickPython,
    [switch]$SkipFrontend
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot
$env:PYTHONPATH = "."

$totalStart = Get-Date
$failures = @()

function Step {
    param(
        [string]$Name,
        [scriptblock]$Block
    )
    Write-Host "" -ForegroundColor White
    Write-Host "==> $Name" -ForegroundColor Cyan
    $start = Get-Date
    try {
        & $Block
        $elapsed = [math]::Round(((Get-Date) - $start).TotalSeconds, 1)
        Write-Host "  OK ($elapsed s)" -ForegroundColor Green
    } catch {
        $elapsed = [math]::Round(((Get-Date) - $start).TotalSeconds, 1)
        Write-Host "  FAIL ($elapsed s)" -ForegroundColor Red
        $script:failures += "$Name (after $elapsed s)"
    }
}

Step "ruff check src/" {
    & .\.venv\Scripts\ruff.exe check src/ --no-fix --output-format=concise
    if ($LASTEXITCODE -ne 0) { throw "ruff falhou" }
}

Step "lint-imports (module boundary contracts)" {
    # Q.66.A.1 — import-linter (config em pyproject.toml). 3 contracts:
    # shared layer base, cpo n.o importa profit, governance n.o importa plan.
    $env:PYTHONPATH = "."
    & .\.venv\Scripts\lint-imports.exe
    if ($LASTEXITCODE -ne 0) { throw "lint-imports falhou" }
}

if (-not $QuickPython) {
    Step "pytest tests/governance + tests/shared (canary)" {
        & .\.venv\Scripts\python.exe -m pytest tests/governance/ tests/shared/ -q --tb=no
        if ($LASTEXITCODE -ne 0) { throw "pytest canary falhou" }
    }
}

Step "verify_invariants.py (estatica + AST)" {
    $env:VERIFY_INVARIANTS_SKIP_TESTS = "1"
    & .\.venv\Scripts\python.exe scripts/verify_invariants.py
    if ($LASTEXITCODE -ne 0) { throw "verify_invariants falhou" }
}

Step ("lint drift gate (BLE001 + Q61.07 + Q61.28)") {
    & .\.venv\Scripts\python.exe scripts/lint_drift_gate.py
    if ($LASTEXITCODE -ne 0) { throw "lint drift gate cresceu - reverter ou actualizar baseline" }
}

if (-not $SkipFrontend) {
    Push-Location frontend
    try {
        Step "tsc -b --noEmit (frontend)" {
            & npx.cmd tsc -b --noEmit
            if ($LASTEXITCODE -ne 0) { throw "tsc falhou" }
        }
        Step "vitest run (frontend)" {
            & npm.cmd test -- --run
            if ($LASTEXITCODE -ne 0) { throw "vitest falhou" }
        }
        Step "lint:mocks (frontend)" {
            & npm.cmd run lint:mocks
            if ($LASTEXITCODE -ne 0) { throw "lint:mocks falhou" }
        }
    } finally {
        Pop-Location
    }
}

$totalElapsed = [math]::Round(((Get-Date) - $totalStart).TotalSeconds, 1)
Write-Host "" -ForegroundColor White
if ($failures.Count -gt 0) {
    Write-Host "FAILED (total $totalElapsed s):" -ForegroundColor Red
    foreach ($f in $failures) { Write-Host "  - $f" -ForegroundColor Red }
    exit 1
} else {
    Write-Host "ALL GREEN ($totalElapsed s)" -ForegroundColor Green
    exit 0
}
