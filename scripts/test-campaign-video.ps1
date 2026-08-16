$ErrorActionPreference = "Stop"
$tests = @(
    "tests/test_campaign_video_execution.py",
    "tests/test_campaign_video_dependencies.py",
    "tests/test_campaign_video_workers.py",
    "tests/test_campaign_video_recovery.py",
    "tests/test_campaign_video_replacement.py",
    "tests/test_campaign_video_cross_channel.py",
    "tests/test_campaign_video_partial.py",
    "tests/test_campaign_video_security.py",
    "tests/test_campaign_video_privacy.py",
    "tests/test_campaign_video_storage.py"
)
foreach ($testPath in $tests) {
    & (Join-Path $PSScriptRoot "test-api-integration.ps1") -TestPath $testPath
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
exit 0