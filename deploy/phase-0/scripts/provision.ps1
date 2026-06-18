# provision.ps1 — Generate .env for Asuralab Phase 0 (Windows PowerShell)
# Usage: .\scripts\provision.ps1 [-Email admin@example.com] [-Password yourpassword]
# Requires: Node.js (preferred) or Docker Desktop running

param(
    [string]$Email          = "admin@asuralab.io",
    [SecureString]$Password = $null,
    [string]$FirstName      = "Admin",
    [string]$LastName       = "Asuralab"
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$EnvFile   = Join-Path (Split-Path -Parent $ScriptDir) ".env"

# --- Resolve plain-text password (needed only for bcrypt hashing) ---
if ($null -eq $Password -or $Password.Length -eq 0) {
    $chars         = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#%^&*'
    $PlainPassword = -join ((1..20) | ForEach-Object { $chars[(Get-Random -Maximum $chars.Length)] })
    Write-Host "[provision] Generated password: $PlainPassword"
} else {
    $PlainPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($Password)
    )
}

# --- Guard: don't overwrite existing .env without confirmation ---
if (Test-Path $EnvFile) {
    $confirm = Read-Host "[provision] .env already exists. Overwrite? [y/N]"
    if ($confirm -notmatch '^[Yy]$') {
        Write-Host "[provision] Aborted."
        exit 0
    }
}

# --- Generate bcrypt hash (Node.js preferred, Docker fallback) ---
Write-Host "[provision] Generating bcrypt hash (rounds=12)..."
$env:PROVISION_PW = $PlainPassword
$OwnerPasswordHash = node -e "const b=require('bcryptjs'); console.log(b.hashSync(process.env.PROVISION_PW, 12));" 2>$null
$env:PROVISION_PW = $null

if (-not $OwnerPasswordHash -or $LASTEXITCODE -ne 0) {
    Write-Host "[provision] Node.js bcryptjs not found, trying Docker..."
    $PythonScript = "import bcrypt,sys; pw=sys.stdin.read().strip().encode(); print(bcrypt.hashpw(pw, bcrypt.gensalt(12)).decode())"
    $OwnerPasswordHash = $PlainPassword | docker run --rm -i python:3.11-alpine sh -c "pip install bcrypt -q 2>/dev/null; python -c `"$PythonScript`""
    if ($LASTEXITCODE -ne 0) { throw "Failed to generate bcrypt hash. Ensure Node.js (with bcryptjs) or Docker is available." }
}

# Docker Compose env_file also substitutes $VAR inside values, which corrupts
# bcrypt hashes ($2a$12$...). Escape each $ as $$ so Compose decodes it back
# to a single $ when passing to the container.
$OwnerPasswordHash = $OwnerPasswordHash -replace '\$', '$$$$'

# --- Generate random secrets (alphanumeric only — no $ so safe for Compose) ---
Write-Host "[provision] Generating random secrets..."
$chars32           = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
$PostgresPassword  = -join ((1..32) | ForEach-Object { $chars32[(Get-Random -Maximum $chars32.Length)] })
$N8nEncryptionKey  = -join ((1..32) | ForEach-Object { $chars32[(Get-Random -Maximum $chars32.Length)] })

# --- Write .env ---
# IMPORTANT: Variables use actual n8n env var names so they can be passed via
# env_file directly to the container, bypassing Compose interpolation.
# This avoids Compose treating $ in bcrypt hashes as variable references.
$timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$envContent = @"
# Asuralab Phase 0 - Auto-generated on $timestamp
# DO NOT COMMIT THIS FILE

# --- Compose interpolation vars (postgres service) ---
POSTGRES_USER=n8n
POSTGRES_PASSWORD=$PostgresPassword
POSTGRES_DB=n8n
N8N_PORT=5678

# --- n8n container vars (passed via env_file, NOT Compose interpolation) ---
# These use actual n8n env var names and are safe to contain $ characters.
N8N_INSTANCE_OWNER_MANAGED_BY_ENV=true
N8N_INSTANCE_OWNER_EMAIL=$Email
N8N_INSTANCE_OWNER_PASSWORD_HASH=$OwnerPasswordHash
N8N_INSTANCE_OWNER_FIRST_NAME=$FirstName
N8N_INSTANCE_OWNER_LAST_NAME=$LastName
N8N_ENCRYPTION_KEY=$N8nEncryptionKey
N8N_HOST=localhost
N8N_PROTOCOL=http
WEBHOOK_URL=http://localhost:5678
N8N_LOG_LEVEL=info
N8N_PERSONALIZATION_ENABLED=false
"@

Set-Content -Path $EnvFile -Value $envContent -Encoding utf8

Write-Host ""
Write-Host "=========================================="
Write-Host "[provision] Done."
Write-Host "  Owner email : $Email"
Write-Host "  Password    : $PlainPassword"
Write-Host "  .env path   : $EnvFile"
Write-Host "=========================================="
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. docker compose up -d"
Write-Host "  2. Wait ~10 seconds, then run:"
Write-Host "     .\scripts\dismiss-survey.ps1 -Email '$Email' -Password '<your-password>'"
