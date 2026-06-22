param([string]$ContainerName = "phase-0-n8n-1")

$ErrorActionPreference = "Stop"
$RepoRoot  = Resolve-Path "$PSScriptRoot\..\.."
$NodesBase = "$RepoRoot\packages\nodes-base"
$CliDist   = "$RepoRoot\packages\cli\dist"
$ContainerBase = "/usr/local/lib/node_modules/n8n/node_modules/n8n-nodes-base"
$ContainerCli  = "/usr/local/lib/node_modules/n8n/dist"

# Cek container running
$running = docker ps --format "{{.Names}}" | Where-Object { $_ -eq $ContainerName }
if (-not $running) {
    Write-Host "ERROR: Container tidak running. Jalankan docker compose up -d dulu." -ForegroundColor Red
    exit 1
}

Write-Host "Deploy custom nodes ke $ContainerName ..." -ForegroundColor Cyan

# Buat folder AgentMST di container
docker exec -u root $ContainerName mkdir -p "$ContainerBase/dist/nodes/AgentMST"

# Copy JS dan JSON node
$nodeDir = "$NodesBase\dist\nodes\AgentMST"
docker cp "$nodeDir\AgentMST.node.js"   "${ContainerName}:${ContainerBase}/dist/nodes/AgentMST/AgentMST.node.js"
docker cp "$nodeDir\AgentMST.node.json" "${ContainerName}:${ContainerBase}/dist/nodes/AgentMST/AgentMST.node.json"
Write-Host "  Copied: AgentMST.node.js + AgentMST.node.json" -ForegroundColor Gray

# Copy node-definitions
$defDir = "$NodesBase\dist\node-definitions\nodes\n8n-nodes-base\agentMST"
$defDest = "$ContainerBase/dist/node-definitions/nodes/n8n-nodes-base/agentMST"
docker exec -u root $ContainerName mkdir -p $defDest
Get-ChildItem $defDir | ForEach-Object {
    docker cp $_.FullName "${ContainerName}:${defDest}/$($_.Name)"
}
Write-Host "  Copied: node-definitions" -ForegroundColor Gray

# Sync package.json
docker cp "$NodesBase\package.json" "${ContainerName}:${ContainerBase}/package.json"
Write-Host "  Copied: package.json" -ForegroundColor Gray

# Copy chat-hub services (termasuk misikaAi provider fix)
$chatHubFiles = @(
    "chat-hub-workflow.service.js",
    "chat-hub.service.js",
    "mst-agent.service.js"
)
foreach ($f in $chatHubFiles) {
    $src = "$CliDist\modules\chat-hub\$f"
    if (Test-Path $src) {
        docker cp $src "${ContainerName}:${ContainerCli}/modules/chat-hub/$f"
        Write-Host "  Copied: $f" -ForegroundColor Gray
    }
}

# Copy LmChatMistikaAi node (fix auth header x-api-key + URL rewrite + model fallback)
$langchainSrc = "$RepoRoot\packages\@n8n\nodes-langchain\dist"
$langchainDest = "/usr/local/lib/node_modules/n8n/node_modules/@n8n/n8n-nodes-langchain"
$misikaNodeSrc = "$langchainSrc\nodes\llms\LmChatMistikaAi\LmChatMistikaAi.node.js"
if (Test-Path $misikaNodeSrc) {
    docker exec -u root $ContainerName mkdir -p "$langchainDest/dist/nodes/llms/LmChatMistikaAi"
    docker cp $misikaNodeSrc "${ContainerName}:${langchainDest}/dist/nodes/llms/LmChatMistikaAi/LmChatMistikaAi.node.js"
    Write-Host "  Copied: LmChatMistikaAi.node.js" -ForegroundColor Gray
}
$misikaCredSrc = "$langchainSrc\credentials\MistikaAiApi.credentials.js"
if (Test-Path $misikaCredSrc) {
    docker exec -u root $ContainerName mkdir -p "$langchainDest/dist/credentials"
    docker cp $misikaCredSrc "${ContainerName}:${langchainDest}/dist/credentials/MistikaAiApi.credentials.js"
    Write-Host "  Copied: MistikaAiApi.credentials.js" -ForegroundColor Gray
}

# Restart container
Write-Host "  Restart $ContainerName ..." -ForegroundColor Yellow
docker restart $ContainerName | Out-Null

# Tunggu sampai ready
Write-Host "  Menunggu n8n siap ..." -ForegroundColor Gray
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 2
    $log = docker logs $ContainerName --tail 3 2>&1
    if ($log -match "accessible via") { break }
}

Write-Host ""
Write-Host "Selesai! Buka http://localhost:5678 dan cari node MST Agent" -ForegroundColor Green
