param([string]$OutputDirectory = "release")
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
if ($env:OS -ne "Windows_NT") { throw "Run this build on Windows." }

python -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw "Regression tests failed." }
python -m PyInstaller --noconfirm --clean build.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

New-Item -ItemType Directory -Force $OutputDirectory | Out-Null
$output = (Resolve-Path $OutputDirectory).Path
# Remove the obsolete connector bundle from a previous build in this output.
$obsoleteConnector = Join-Path $output "RaahiChromeExtension"
if (Test-Path $obsoleteConnector) { Remove-Item $obsoleteConnector -Recurse -Force }
Copy-Item dist/RaahiScraper.exe (Join-Path $output "RaahiScraper.exe") -Force
Copy-Item WINDOWS_QUICK_START.txt (Join-Path $output "WINDOWS_QUICK_START.txt") -Force
$exe = Join-Path $output "RaahiScraper.exe"
$report = Join-Path $output "windows-packaging-check.json"
$arguments = @("--self-test", "--report", "`"$report`"")
$process = Start-Process -FilePath $exe -ArgumentList $arguments -PassThru
if (-not $process.WaitForExit(120000)) {
    $process.Kill()
    throw "Packaged executable check timed out."
}
if ($process.ExitCode -ne 0) {
    if (Test-Path $report) { Get-Content $report }
    throw "Packaged executable check failed: $($process.ExitCode)"
}
$check = Get-Content $report -Raw | ConvertFrom-Json
if (-not $check.passed -or -not $check.frozen -or $check.platform -ne 'win32') {
    throw "Missing successful Windows executable validation."
}

$hash = (Get-FileHash $exe -Algorithm SHA256).Hash.ToLowerInvariant()
"$hash  RaahiScraper.exe" | Set-Content (Join-Path $output "SHA256SUMS.txt") -Encoding ascii
$commit = git rev-parse HEAD
python -m pip freeze | Set-Content (Join-Path $output "dependencies.txt") -Encoding utf8
@{
    source_commit = $commit
    architecture = "Windows x64"
    executable_sha256 = $hash
    regression_test_suite_passed = $true
    automated_packaging_check_passed = $true
    live_client_chrome_tested = $false
    signed = $false
    built_at_utc = [DateTime]::UtcNow.ToString("o")
} | ConvertTo-Json | Set-Content (Join-Path $output "build-info.json") -Encoding utf8
Write-Host "Windows executable validated: $exe"
