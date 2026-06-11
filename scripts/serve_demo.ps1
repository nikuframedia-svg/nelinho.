<#
  serve_demo.ps1  —  Arranque idempotente do nelinho para a demo remota (Tailscale).

  Sobe (ou repara) toda a stack na ordem certa e SÓ arranca o que estiver em baixo:
    Docker (pg/redis/cube)  ->  Ollama  ->  backend :8001  ->  1 worker arq  ->  Caddy (tailnet :80)

  Idempotente: pode correr à vontade (logon, crash-recovery de 10 em 10 min, ou à mão).
  Tailnet-only: o Caddy faz bind no IP do tailnet; nada fica exposto na rede de casa.

  Correr à mão:  powershell -ExecutionPolicy Bypass -File scripts\serve_demo.ps1
#>

$ErrorActionPreference = 'Continue'
$repo    = 'C:\Users\User\nelinho'
$py      = Join-Path $repo '.venv\Scripts\python.exe'
$caddyCfg= Join-Path $repo 'deploy\Caddyfile.tailscale'
$tsExe   = 'C:\Program Files\Tailscale\tailscale.exe'
$ollama  = 'C:\Users\User\AppData\Local\Programs\Ollama\ollama.exe'
$caddyExe= (Get-Command caddy -ErrorAction SilentlyContinue).Source
if (-not $caddyExe) { $caddyExe = 'C:\Users\User\scoop\shims\caddy.exe' }
$expectIp= '100.75.136.9'
$containers = @('prodplan-pg-wsl','nelo-redis','prodplan-cube')

function Log($m){ Write-Host ("[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m) }

function Test-Http($url, $timeoutSec = 4) {
  try { $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec $timeoutSec; return ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) }
  catch { return $false }
}

function Rotate-Log([string]$path, [int]$keep = 5) {
  # Q.173.T — Start-Process TRUNCA o ficheiro redirecionado a cada arranque,
  # apagando a evidencia operacional (o veto CP-SAT de 2026-06-10 perdeu-se
  # assim — auditoria 2026-06-11). Ring de $keep geracoes: x -> x.1 -> x.2 ...
  if (-not (Test-Path $path)) { return }
  if ((Get-Item $path).Length -eq 0) { return }
  for ($i = $keep - 1; $i -ge 1; $i--) {
    $src = "$path.$i"; $dst = "$path.$($i + 1)"
    if (Test-Path $src) { Move-Item -Force $src $dst }
  }
  Move-Item -Force $path "$path.1"
}

# --- pre-checks ---------------------------------------------------------------
if (-not (Test-Path $py))       { Log "ERRO: venv python nao encontrado em $py"; exit 1 }
if (-not (Test-Path $caddyCfg)) { Log "ERRO: Caddyfile nao encontrado em $caddyCfg"; exit 1 }
$env:PYTHONPATH = $repo

# --- 1. Docker (pg / redis / cube) -------------------------------------------
Log "Docker: aguardar engine..."
$dockerOk = $false
for ($i=0; $i -lt 30; $i++) {
  docker info *> $null
  if ($?) { $dockerOk = $true; break }
  Start-Sleep -Seconds 4
}
if (-not $dockerOk) { Log "AVISO: Docker engine nao respondeu (Docker Desktop arranca no login). Continuo na esperanca de que suba." }
foreach ($c in $containers) {
  $state = (docker inspect -f '{{.State.Running}}' $c 2>$null)
  if ($state -ne 'true') { Log "Docker: a arrancar $c"; docker start $c *> $null } else { Log "Docker: $c ja a correr" }
}

# Postgres pronto?
Log "Postgres: aguardar pg_isready..."
for ($i=0; $i -lt 30; $i++) {
  docker exec prodplan-pg-wsl pg_isready -U prodplan *> $null
  if ($?) { Log "Postgres pronto"; break }
  Start-Sleep -Seconds 3
}

# --- 2. Ollama ----------------------------------------------------------------
if (Test-Http 'http://127.0.0.1:11434/api/tags') {
  Log "Ollama: ja a servir"
} else {
  Log "Ollama: a arrancar serve"
  if (Test-Path $ollama) { Start-Process -FilePath $ollama -ArgumentList 'serve' -WindowStyle Hidden }
  for ($i=0; $i -lt 15; $i++) { if (Test-Http 'http://127.0.0.1:11434/api/tags') { break }; Start-Sleep -Seconds 2 }
}

# --- 3. Backend :8001 ---------------------------------------------------------
# Idempotencia por PORTO (nao por contagem de processos): cada `python -m uvicorn`
# corre como par parent+child, por isso contar processos engana. Se o :8001 estiver
# em LISTEN, o backend esta de pe. Senao, mata orfaos e arranca limpo.
$port8001 = Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue
if ($port8001) {
  Log "Backend: ja a escutar em :8001 (pid $($port8001.OwningProcess))"
} else {
  $orphans = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*uvicorn src.main:app*' })
  if ($orphans.Count -gt 0) { Log ("Backend: limpar {0} proc(s) uvicorn orfaos (porto livre)" -f $orphans.Count); $orphans | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; Start-Sleep -Seconds 2 }
  Log "Backend: a arrancar uvicorn (127.0.0.1:8001)"
  Rotate-Log (Join-Path $repo '_backend.out'); Rotate-Log (Join-Path $repo '_backend.err')
  Start-Process -FilePath $py `
    -ArgumentList @('-m','uvicorn','src.main:app','--host','127.0.0.1','--port','8001','--log-level','warning') `
    -WorkingDirectory $repo -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $repo '_backend.out') `
    -RedirectStandardError  (Join-Path $repo '_backend.err')
  $up = $false
  for ($i=0; $i -lt 40; $i++) { if (Test-Http 'http://127.0.0.1:8001/health') { $up=$true; break }; Start-Sleep -Seconds 2 }
  if ($up) { Log "Backend pronto" } else { Log "AVISO: backend nao respondeu a tempo (ver _backend.err)" }
}

# --- 4. Worker arq (1 worker logico) -----------------------------------------
# `python -m arq` tambem corre como par parent+child => 2 procs = 1 worker.
# 0 procs -> arrancar; 1-2 procs -> 1 worker saudavel; >2 -> reset para 1.
$arq = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*arq src.plan.cpo.worker*' })
if ($arq.Count -eq 0) {
  Log "Worker arq: nenhum -> a arrancar 1"
  Rotate-Log (Join-Path $repo '_arq.out'); Rotate-Log (Join-Path $repo '_arq.err')
  Start-Process -FilePath $py `
    -ArgumentList @('-m','arq','src.plan.cpo.worker.WorkerSettings') `
    -WorkingDirectory $repo -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $repo '_arq.out') `
    -RedirectStandardError  (Join-Path $repo '_arq.err')
} elseif ($arq.Count -le 2) {
  Log ("Worker arq: 1 worker a correr ({0} proc parent+child) (ok)" -f $arq.Count)
} else {
  Log ("Worker arq: {0} procs => >1 worker -> reset para 1" -f $arq.Count)
  $arq | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
  Start-Sleep -Seconds 2
  Rotate-Log (Join-Path $repo '_arq.out'); Rotate-Log (Join-Path $repo '_arq.err')
  Start-Process -FilePath $py `
    -ArgumentList @('-m','arq','src.plan.cpo.worker.WorkerSettings') `
    -WorkingDirectory $repo -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $repo '_arq.out') `
    -RedirectStandardError  (Join-Path $repo '_arq.err')
}

# --- 5. Caddy (tailnet :80) ---------------------------------------------------
$ip = (& $tsExe ip -4 2>$null | Select-Object -First 1)
if ($ip -and $ip.Trim() -ne $expectIp) {
  Log "AVISO: IP tailnet=$ip difere do esperado $expectIp no Caddyfile.tailscale (bind vai falhar ate corrigires a linha 'bind')."
}
$caddyProc = Get-Process caddy -ErrorAction SilentlyContinue
if ($caddyProc) {
  Log "Caddy: ja a correr"
} else {
  Log "Caddy: a arrancar (config $caddyCfg)"
  Push-Location $repo
  & $caddyExe start --config $caddyCfg 2>&1 | ForEach-Object { Log "caddy> $_" }
  Pop-Location
}

# --- 6. Relatorio -------------------------------------------------------------
Start-Sleep -Seconds 2
$bH = if (Test-Http 'http://127.0.0.1:8001/health') { 'OK' } else { 'DOWN' }
$bR = if (Test-Http 'http://127.0.0.1:8001/health/ready') { 'OK' } else { 'DEGRADED/DOWN' }
$tn = if (Test-Http ("http://{0}/" -f $expectIp)) { 'OK' } else { 'DOWN' }
$arqN = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*arq src.plan.cpo.worker*' }).Count
$arqS = if ($arqN -eq 0) { 'DOWN (0)' } elseif ($arqN -le 2) { "OK (1 worker, $arqN proc)" } else { "PROBLEMA (>1 worker, $arqN proc)" }
Log "================ ESTADO ================"
Log ("Backend  /health      : {0}" -f $bH)
Log ("Backend  /health/ready: {0}" -f $bR)
Log ("Worker arq            : {0}" -f $arqS)
Log ("Caddy tailnet http://{0}/ : {1}" -f $expectIp, $tn)
Log ("URL demo (tailnet)     : http://{0}/  ou  http://asus.tail8a0cf7.ts.net/" -f $expectIp)
Log "======================================="
