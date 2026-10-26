param(
  [Parameter(Mandatory = $true)][string]$DatabaseDump,
  [Parameter(Mandatory = $true)][ValidatePattern('^\d{8}T\d{6}Z-[a-f0-9]{12}$')][string]$BackupId,
  [string]$ExpectedEvidencePath,
  [string]$ExpectedSnapshotPath,
  [string]$ReportPath
)
$ErrorActionPreference = "Stop"
$dumpPath = (Resolve-Path -LiteralPath $DatabaseDump).Path
$expectedPairProvided = [bool]$ExpectedEvidencePath -and [bool]$ExpectedSnapshotPath
if (([bool]$ExpectedEvidencePath -xor [bool]$ExpectedSnapshotPath) -or ($ReportPath -and -not $expectedPairProvided)) {
  throw "Canonical restore comparison requires both ExpectedEvidencePath and ExpectedSnapshotPath."
}
$docker = Get-Command docker -ErrorAction SilentlyContinue
if (-not $docker -and $env:PC_CERT_DOCKER_PATH -and (Test-Path -LiteralPath $env:PC_CERT_DOCKER_PATH)) {
  $docker = [pscustomobject]@{ Source = $env:PC_CERT_DOCKER_PATH }
}
if (-not $docker) { throw "Docker Desktop is required for the isolated disposable restore rehearsal." }
$container = "vayujit-pc-restore-$BackupId"
$volume = "vayujit-pc-restore-$BackupId"
$labelKey = "vayujit.pc.restore-check"
$volumeCreated = $false
$containerCreated = $false
$passwordBytes = New-Object byte[] 32
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try { $rng.GetBytes($passwordBytes) } finally { $rng.Dispose() }
$password = [BitConverter]::ToString($passwordBytes).Replace("-", "").ToLowerInvariant()
$restoreTimer = [System.Diagnostics.Stopwatch]::StartNew()
$checks = [System.Collections.Generic.List[object]]::new()
$financialPrecisionVerified = $false
$canonicalRecordsMatched = $false
try {
  & $docker.Source inspect $container *> $null
  if ($LASTEXITCODE -eq 0) { throw "restore_container_name_already_exists" }
  & $docker.Source volume inspect $volume *> $null
  if ($LASTEXITCODE -eq 0) { throw "restore_volume_name_already_exists" }
  $createdName = & $docker.Source volume create --label "$labelKey=$BackupId" $volume
  if ($LASTEXITCODE -ne 0 -or $createdName -ne $volume) { throw "restore_volume_create_failed" }
  $volumeCreated = $true
  & $docker.Source run --detach --name $container --label "$labelKey=$BackupId" --network none --mount "type=volume,source=$volume,target=/var/lib/postgresql/data" --env "POSTGRES_DB=vayujit_restore_check" --env "POSTGRES_USER=postgres" --env "POSTGRES_PASSWORD=$password" postgres:17-alpine | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "restore_container_create_failed" }
  $containerCreated = $true

  $ready = $false
  for ($attempt = 0; $attempt -lt 60; $attempt++) {
    & $docker.Source exec $container pg_isready -U postgres -d vayujit_restore_check *> $null
    if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    Start-Sleep -Seconds 2
  }
  if (-not $ready) { throw "restore_postgres_not_ready" }

  $containerDump = "/tmp/$BackupId.dump"
  & $docker.Source cp $dumpPath "$container`:$containerDump"
  if ($LASTEXITCODE -ne 0) { throw "restore_dump_copy_failed" }
  & $docker.Source exec $container pg_restore --exit-on-error --no-owner --no-privileges -U postgres -d vayujit_restore_check $containerDump
  if ($LASTEXITCODE -ne 0) { throw "independent_database_restore_failed" }

  $revision = (& $docker.Source exec $container psql -U postgres -d vayujit_restore_check -Atc "SELECT version_num FROM alembic_version LIMIT 1") -join ""
  if ($LASTEXITCODE -ne 0 -or -not $revision) { throw "restored_migration_revision_missing" }
  $ownerConstraint = (& $docker.Source exec $container psql -U postgres -d vayujit_restore_check -Atc "SELECT count(*) FROM pg_constraint WHERE conname = 'ck_users_single_owner'") -join ""
  if ($LASTEXITCODE -ne 0 -or $ownerConstraint -ne "1") { throw "restored_single_owner_constraint_missing" }
  $checks.Add([ordered]@{ name = "migration_revision_present"; pass = $true })
  $checks.Add([ordered]@{ name = "single_owner_constraint_preserved"; pass = $true })
  if ($expectedPairProvided) {
    $expected = Get-Content -LiteralPath $ExpectedEvidencePath -Raw | ConvertFrom-Json
    foreach ($field in @("owner_id", "product_id", "inventory_item_id", "financial_cost_id", "media_id")) {
      if ([string]$expected.$field -notmatch '^[0-9a-fA-F-]{36}$') { throw "Expected disposable evidence has an invalid $field identifier." }
    }
    $ownerId = [string]$expected.owner_id
    $productId = [string]$expected.product_id
    $inventoryId = [string]$expected.inventory_item_id
    $costId = [string]$expected.financial_cost_id
    $mediaId = [string]$expected.media_id
    $sql = @"
SELECT jsonb_build_object(
  'owner_count', (SELECT count(*) FROM users),
  'owner_id', (SELECT id::text FROM users WHERE id='$ownerId'),
  'product', (SELECT jsonb_build_object('id',id::text,'name',name,'sku',sku,'price',price_amount::text,'price_currency',price_currency,'cost',cost_amount::text,'inventory_quantity',inventory_quantity) FROM products WHERE id='$productId'),
  'financial_cost', (SELECT jsonb_build_object('id',id::text,'amount',amount::text,'currency',currency,'cost_type',cost_type,'evidence_status',evidence_status) FROM financial_cost_evidence WHERE id='$costId'),
  'inventory_item', (SELECT jsonb_build_object('id',id::text,'product_id',product_id::text,'sku',internal_sku,'location',location_code,'on_hand',on_hand_quantity,'reserved',reserved_quantity,'damaged',damaged_quantity,'version',version) FROM inventory_items WHERE id='$inventoryId'),
  'inventory_movements', (SELECT count(*) FROM inventory_movements WHERE inventory_item_id='$inventoryId'),
  'media_asset', (SELECT jsonb_build_object('id',id::text,'checksum',checksum_sha256,'size_bytes',size_bytes,'mime_type',mime_type,'status',status) FROM media_assets WHERE id='$mediaId'),
  'catalog_image', (SELECT jsonb_build_object('media_id',media_id::text,'alt_text',alt_text,'position',position,'is_primary',is_primary) FROM catalog_product_images WHERE product_id='$productId' AND media_id='$mediaId'),
  'audit_events', (SELECT count(*) FROM audit_events WHERE actor_id='$ownerId' AND entity_id IN ('$productId','$inventoryId','$costId','$mediaId'))
)::text;
"@
    $restoredSnapshotText = (& $docker.Source exec $container psql -U postgres -d vayujit_restore_check -Atc $sql) -join ""
    if ($LASTEXITCODE -ne 0 -or -not $restoredSnapshotText) { throw "restored_canonical_snapshot_query_failed" }
    $restoredSnapshot = $restoredSnapshotText | ConvertFrom-Json
    $sourceSnapshotText = Get-Content -LiteralPath $ExpectedSnapshotPath -Raw
    $sourceSnapshot = $sourceSnapshotText | ConvertFrom-Json
    $canonicalRecordsMatched = ($restoredSnapshotText | ConvertFrom-Json | ConvertTo-Json -Depth 12 -Compress) -ceq ($sourceSnapshotText | ConvertFrom-Json | ConvertTo-Json -Depth 12 -Compress)
    if (-not $canonicalRecordsMatched) { throw "canonical_restored_records_do_not_match_source_snapshot" }
    $financialPrecisionVerified = [string]$restoredSnapshot.financial_cost.amount -eq "120.00" -and
      [string]$restoredSnapshot.product.price -eq "299.00" -and
      [string]$restoredSnapshot.product.cost -eq "120.00"
    if (-not $financialPrecisionVerified) { throw "financial_decimal_precision_mismatch_after_restore" }
    $checks.Add([ordered]@{ name = "canonical_owner_product_inventory_finance_media_audit_rows_match"; pass = $canonicalRecordsMatched })
    $checks.Add([ordered]@{ name = "financial_decimal_precision_preserved"; pass = $financialPrecisionVerified })
    $checks.Add([ordered]@{ name = "audit_events_restored"; pass = ([int]$restoredSnapshot.audit_events -gt 0) })
    if ([int]$restoredSnapshot.audit_events -lt 1) { throw "audit_events_missing_after_restore" }
  }
  $restoreTimer.Stop()
  $result = [ordered]@{
    status = "PASS"
    migration_revision = $revision
    single_owner_constraint = $true
    canonical_records_matched = $canonicalRecordsMatched
    financial_precision_verified = $financialPrecisionVerified
    duration_seconds = [Math]::Round($restoreTimer.Elapsed.TotalSeconds, 3)
    checks = @($checks)
  }
  if ($ReportPath) {
    $reportFull = [System.IO.Path]::GetFullPath($ReportPath)
    if (-not $reportFull.StartsWith([System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath()), [System.StringComparison]::OrdinalIgnoreCase)) {
      throw "Restore report output must remain under the system temporary directory."
    }
    [System.IO.File]::WriteAllText($reportFull, (($result | ConvertTo-Json -Depth 8) + "`n"), [System.Text.UTF8Encoding]::new($false))
  }
  Write-Output ($result | ConvertTo-Json -Depth 8 -Compress)
} finally {
  if ($containerCreated) {
    $containerLabel = (& $docker.Source inspect --format "{{ index .Config.Labels `"$labelKey`" }}" $container) -join ""
    if ($LASTEXITCODE -eq 0 -and $containerLabel -eq $BackupId -and $container -eq "vayujit-pc-restore-$BackupId") {
      & $docker.Source rm --force $container *> $null
    } else {
      Write-Warning "Disposable restore container marker did not match; container kept for manual review: $container"
    }
  }
  if ($volumeCreated) {
    $format = '{{ index .Labels "vayujit.pc.restore-check" }}'
    $label = (& $docker.Source volume inspect --format $format $volume) -join ""
    if ($LASTEXITCODE -eq 0 -and $label -eq $BackupId -and $volume -eq "vayujit-pc-restore-$BackupId") {
      & $docker.Source volume rm $volume *> $null
    } else {
      Write-Warning "Disposable restore volume marker did not match; volume kept for manual review: $volume"
    }
  }
}
