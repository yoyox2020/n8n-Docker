# dismiss-survey.ps1 — Mark personalization survey as completed for a user
# Run once after "docker compose up -d" to prevent the survey popup appearing.
# Usage: .\scripts\dismiss-survey.ps1 -Email admin@asuralab.io -Password yourpassword
#
# Background: n8n shows "Customize n8n to you" survey when personalizationAnswers
# is null on the user record. Submitting dummy answers prevents it permanently.

param(
    [string]$Email     = "admin@asuralab.io",
    [SecureString]$Password = $null,
    [string]$N8nUrl    = "http://localhost:5678"
)

$ErrorActionPreference = "Stop"

if ($null -eq $Password -or $Password.Length -eq 0) {
    $Password = Read-Host "Password for $Email" -AsSecureString
}
$PlainPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($Password)
)

Write-Host "[dismiss-survey] Logging in as $Email ..."

$loginBody = @{ emailOrLdapLoginId = $Email; password = $PlainPassword } | ConvertTo-Json
try {
    $loginResp = Invoke-RestMethod -Uri "$N8nUrl/rest/login" -Method POST `
        -ContentType "application/json" -Body $loginBody -SessionVariable sv
} catch {
    throw "Login failed: $($_.Exception.Message). Is n8n running at $N8nUrl ?"
}

if ($loginResp.data.personalizationAnswers) {
    Write-Host "[dismiss-survey] Survey already answered — nothing to do."
    exit 0
}

Write-Host "[dismiss-survey] Submitting dummy survey answers ..."
$surveyBody = @{
    version                              = "v4"
    personalization_survey_submitted_at  = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    companyType                          = "other"
    companySize                          = "1-5"
    automationGoal                       = "other"
    role                                 = "IT Manager"
    reportedSource                       = "other"
} | ConvertTo-Json

Invoke-RestMethod -Uri "$N8nUrl/rest/me/survey" -Method POST `
    -ContentType "application/json" -Body $surveyBody -WebSession $sv | Out-Null

Write-Host "[dismiss-survey] Done — personalization survey will not appear again."
