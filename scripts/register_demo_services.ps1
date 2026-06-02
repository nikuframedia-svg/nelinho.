<#
  register_demo_services.ps1 - torna a demo do nelinho permanente (auto-arranque).

  Regista uma tarefa no Agendador (Task Scheduler) que corre scripts\serve_demo.ps1:
    - no LOGON do utilizador (sobrevive a reboot, assumindo que entras na sessao),
    - e repete a cada 10 min (auto-recuperacao se o backend/caddy morrer; idempotente).

  A camada de dados (Postgres/Redis/Cube em Docker, Ollama) ja foi posta a auto-arrancar:
    - containers Docker com --restart unless-stopped (sobem com o Docker Desktop),
    - Docker Desktop e Ollama arrancam no login,
    - Tailscale ja e servico de boot.

  NOTA: para sobreviver a LOGOFF (sessao fechada) seria preciso auto-login do Windows,
  porque o Docker Desktop e login-scoped. Recomendacao: bloquear o ecra (Win+L) em vez
  de fazer logoff. Auto-login e opcional e fica ao teu criterio.

  Correr:  powershell -ExecutionPolicy Bypass -File scripts\register_demo_services.ps1
#>

$ErrorActionPreference = 'Stop'
$repo     = 'C:\Users\User\nelinho'
$script   = Join-Path $repo 'scripts\serve_demo.ps1'
$taskName = 'nelinho-demo'
$me       = "$env:USERDOMAIN\$env:USERNAME"

if (-not (Test-Path $script)) { Write-Host "ERRO: $script nao existe"; exit 1 }

# Path do script sem espacos -> nao precisa de aspas internas.
$arg = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File $script"
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arg -WorkingDirectory $repo

# Dois triggers, ambos com repeticao de 10 min (crash-recovery / auto-reparacao):
#   t1 = no LOGON (cobre reboot/login)
#   t2 = Once agora (cobre a sessao atual ja, sem esperar novo login)
$rep = (New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 10)).Repetition
$t1 = New-ScheduledTaskTrigger -AtLogOn -User $me
$t1.Repetition = $rep
$t2 = New-ScheduledTaskTrigger -Once -At (Get-Date)
$t2.Repetition = $rep

$principal = New-ScheduledTaskPrincipal -UserId $me -LogonType Interactive -RunLevel Limited

$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger @($t1,$t2) -Principal $principal -Settings $settings -Force -Description 'nelinho demo Tailscale: sobe backend/arq/caddy no logon + repara de 10 em 10 min' | Out-Null

Write-Host "OK - tarefa '$taskName' registada."
Get-ScheduledTask -TaskName $taskName | Select-Object TaskName, State | Format-Table -AutoSize | Out-String | Write-Host
$ti = Get-ScheduledTaskInfo -TaskName $taskName
Write-Host ("Proxima execucao: " + $ti.NextRunTime + "  | Ultimo resultado: " + $ti.LastTaskResult)
