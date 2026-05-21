# Q.68.2.C - nelinho daily Postgres backup (Windows dev / on-prem mirror).
#
# Mirror of scripts/backup_db.sh for Windows boxes. Production runs on
# Linux + systemd timer; this script exists so Luis can take an ad-hoc
# dump from the dev box before risky operations (drop+recreate cycles,
# Alembic experiments, schema rewrites).
#
# Usage:
#   .\scripts\backup_db.ps1                                # defaults
#   $env:NELINHO_BACKUP_DIR = 'D:\backups\nelinho'; .\scripts\backup_db.ps1
#
# Environment variables (same names as the Linux script):
#   NELINHO_BACKUP_DIR            default $env:USERPROFILE\nelinho-backups
#   POSTGRES_DB                   default prodplan_one
#   POSTGRES_USER                 default prodplan
#   POSTGRES_HOST                 default localhost
#   POSTGRES_PASSWORD             passed via PGPASSWORD
#   NELINHO_BACKUP_RETENTION_DAYS default 30
#
# Exit codes:
#   0   dump ok + integrity verified
#   1   pg_dump failed
#   2   integrity check failed

$ErrorActionPreference = 'Stop'

function Get-EnvOrDefault {
    param([string]$Name, [string]$Default)
    $value = [Environment]::GetEnvironmentVariable($Name)
    if ([string]::IsNullOrWhiteSpace($value)) { return $Default }
    return $value
}

$BackupDir      = Get-EnvOrDefault 'NELINHO_BACKUP_DIR' (Join-Path $env:USERPROFILE 'nelinho-backups')
$DbName         = Get-EnvOrDefault 'POSTGRES_DB'   'prodplan_one'
$DbUser         = Get-EnvOrDefault 'POSTGRES_USER' 'prodplan'
$DbHost         = Get-EnvOrDefault 'POSTGRES_HOST' 'localhost'
$RetentionDays  = [int](Get-EnvOrDefault 'NELINHO_BACKUP_RETENTION_DAYS' '30')

# Locate pg_dump / pg_restore. Prefer scoop (the path used by CLAUDE.md
# recovery commands) then PATH lookup.
$ScoopBin = Join-Path $env:USERPROFILE 'scoop\apps\postgresql\current\bin'
$PgDump    = if (Test-Path (Join-Path $ScoopBin 'pg_dump.exe'))    { Join-Path $ScoopBin 'pg_dump.exe' }    else { (Get-Command pg_dump.exe    -ErrorAction SilentlyContinue).Source }
$PgRestore = if (Test-Path (Join-Path $ScoopBin 'pg_restore.exe')) { Join-Path $ScoopBin 'pg_restore.exe' } else { (Get-Command pg_restore.exe -ErrorAction SilentlyContinue).Source }

if (-not $PgDump -or -not (Test-Path $PgDump)) {
    Write-Error "pg_dump.exe not found (looked in $ScoopBin and PATH)"
    exit 1
}
if (-not $PgRestore -or -not (Test-Path $PgRestore)) {
    Write-Error "pg_restore.exe not found (looked in $ScoopBin and PATH)"
    exit 1
}

if (-not (Test-Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir | Out-Null
}

$Timestamp  = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$BackupFile = Join-Path $BackupDir "nelinho_${Timestamp}.dump"

function Write-Log { param([string]$Msg) Write-Host "[$([DateTimeOffset]::Now.ToString('o'))] $Msg" }

Write-Log "pg_dump '$DbName' (host=$DbHost user=$DbUser) -> $BackupFile"

# pg_dump (custom format -Fc, compressed, no owner/privs for portable restore).
& $PgDump `
    -h $DbHost `
    -U $DbUser `
    -d $DbName `
    -Fc `
    --no-owner `
    --no-privileges `
    -f $BackupFile

if ($LASTEXITCODE -ne 0) {
    Write-Log "ERROR: pg_dump failed (exit $LASTEXITCODE)"
    if (Test-Path $BackupFile) { Remove-Item $BackupFile -Force }
    exit 1
}

# Integrity: pg_restore --list parses the dump TOC.
& $PgRestore --list $BackupFile *>$null
if ($LASTEXITCODE -ne 0) {
    Write-Log "ERROR: integrity check failed; removing $BackupFile"
    Remove-Item $BackupFile -Force
    exit 2
}

$DumpSize = (Get-Item $BackupFile).Length
$DumpSizeMb = [math]::Round($DumpSize / 1MB, 2)
Write-Log "Backup OK: $BackupFile (${DumpSizeMb} MB)"

# Retention.
$Cutoff = (Get-Date).AddDays(-$RetentionDays)
$Pruned = Get-ChildItem $BackupDir -Filter 'nelinho_*.dump' |
    Where-Object { $_.LastWriteTime -lt $Cutoff }
foreach ($f in $Pruned) {
    Write-Log "Pruning $($f.Name)"
    Remove-Item $f.FullName -Force
}
Write-Log "Retention: pruned $($Pruned.Count) dump(s) older than $RetentionDays days"

exit 0
