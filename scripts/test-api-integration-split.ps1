param([ValidateSet('core','commerce','campaigns')] [string]$Group = 'core')
$ErrorActionPreference = 'Stop'
$groups = @{
  core = @('tests/test_auth_integration.py', 'tests/test_brands_integration.py', 'tests/test_products_integration.py', 'tests/test_media_integration.py', 'tests/test_publishing_integration.py', 'tests/test_workflows_integration.py', 'tests/test_scheduler_integration.py')
  commerce = @('tests/test_commerce_integration.py', 'tests/test_amazon_integration.py', 'tests/test_flipkart_integration.py', 'tests/test_cross_marketplace_e2e.py')
  campaigns = @('tests/test_campaigns_integration.py', 'tests/test_campaign_connectors_e2e.py', 'tests/test_campaign_activity_rescheduling.py')
}
$runner = Join-Path $PSScriptRoot 'test-api-integration.ps1'
foreach ($testPath in $groups[$Group]) {
  & powershell -NoProfile -ExecutionPolicy Bypass -File $runner -TestPath $testPath
  if ($LASTEXITCODE) { exit $LASTEXITCODE }
}
exit 0