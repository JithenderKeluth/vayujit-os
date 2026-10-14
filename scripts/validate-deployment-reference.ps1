param(
  [string]$ComposeFile = "infrastructure/docker-compose.production.yml",
  [string]$EnvFile = "infrastructure/.env.production"
)
$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$compose = Join-Path $repo $ComposeFile
$envPath = Join-Path $repo $EnvFile
$required = @(
  "infrastructure/Dockerfile.api",
  "infrastructure/Dockerfile.web",
  "infrastructure/nginx.web.conf",
  "infrastructure/nginx.production.conf.template",
  "infrastructure/docker-compose.production.yml",
  "infrastructure/production.env.example"
)
foreach ($relative in $required) {
  if (-not (Test-Path (Join-Path $repo $relative))) { throw "Missing deployment artifact: $relative" }
}
$temporaryEnv = $false
if (Test-Path $envPath) {
  $content = Get-Content -Raw $envPath
  if ($content -match "(?im)(PASSWORD|SECRET|TOKEN|KEY)=([^<\r\n]+)" -and $content -notmatch "(?im)<secret|<dedicated|CHANGE_ME") {
    throw "The deployment env file appears to contain a non-placeholder secret. Use a secret manager, not a checked-in file."
  }
  if ((Get-Item $envPath).Length -eq 0) { throw "Deployment env file is empty." }
}
else {
  Write-Warning "No $EnvFile found; Compose will be parsed with temporary non-secret placeholders only. Copy infrastructure/production.env.example into a secret-managed deployment directory before use."
  # Compose still requires the env_file declared by the reference topology to
  # exist.  Create a disposable, non-secret file solely for syntax validation;
  # it is removed in the finally block below and is never suitable for deploy.
  @(
    "POSTGRES_DB=compose_validation"
    "POSTGRES_USER=compose_validation"
    "POSTGRES_PASSWORD=placeholder-only"
    "VAYUJIT_PUBLIC_WEB_DOMAIN=validation.invalid"
    "VAYUJIT_TLS_CERT_DIRECTORY=/var/lib/vayujit/certs"
  ) | Set-Content -Path $envPath -Encoding utf8
  $temporaryEnv = $true
}
try {
  if (Get-Command docker -ErrorAction SilentlyContinue) {
    $args = @("compose", "-f", $compose, "--env-file", $envPath, "config")
    & docker @args | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose rejected the production reference configuration." }
    Write-Output "PASS: Docker Compose reference configuration is syntactically valid."
  } else {
    Write-Warning "Docker is unavailable; skipped compose config validation."
  }
}
finally {
  if ($temporaryEnv -and (Test-Path $envPath)) {
    Remove-Item -LiteralPath $envPath -Force
  }
}
Write-Output "PASS: deployment artifacts and secret placeholders validated."
