param([ValidateSet('Fast', 'Full', 'Security', 'Release')][string]$Mode = 'Fast')
$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$initialDirectory = Get-Location
$initialPlatform = $env:QT_QPA_PLATFORM
$initialCache = $env:UV_CACHE_DIR
function Invoke-Checked {
    param([string[]]$Arguments)
    & uv @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Verification failed: uv $($Arguments -join ' ')" }
}
try {
    Set-Location -LiteralPath $workspace
    $env:UV_CACHE_DIR = Join-Path $workspace '.uv-cache'
    $env:QT_QPA_PLATFORM = 'offscreen'
    New-Item -ItemType Directory -Force reports | Out-Null
    Invoke-Checked -Arguments @('lock', '--check', '--offline')
    Invoke-Checked -Arguments @('run', '--locked', '--all-groups', 'ruff', 'check', '.')
    Invoke-Checked -Arguments @('run', '--locked', '--all-groups', 'ruff', 'format', '--check', '.')
    Invoke-Checked -Arguments @('run', '--locked', '--all-groups', 'pyrefly', 'check')
    Invoke-Checked -Arguments @('run', '--locked', '--all-groups', 'python', 'scripts/check_repository.py')
    $actionlint = Join-Path $workspace 'reports/tools/actionlint.exe'
    if (Test-Path -LiteralPath $actionlint) {
        & $actionlint
        if ($LASTEXITCODE -ne 0) { throw 'Workflow validation failed.' }
    }
    if ($Mode -eq 'Fast') {
        Invoke-Checked -Arguments @('run', '--locked', '--all-groups', '--group', 'test', '--group', 'ui-test', 'pytest', '-q', '-m', 'unit')
    } else {
        Invoke-Checked -Arguments @('run', '--locked', '--all-groups', '--group', 'test', '--group', 'ui-test', 'pytest', '-q', '-m', 'not live and not packaged', '--cov', '--cov-report=json:reports/coverage.json', '--cov-report=xml:reports/coverage.xml', '--junitxml=reports/junit.xml')
        Invoke-Checked -Arguments @('run', '--locked', '--all-groups', 'python', 'scripts/check_coverage.py')
        Invoke-Checked -Arguments @('run', '--locked', '--all-groups', 'python', 'scripts/scan_snapshot.py')
    }
    if ($Mode -in @('Security', 'Release')) {
        Invoke-Checked -Arguments @('run', '--locked', '--all-groups', '--group', 'security', 'bandit', '-c', 'pyproject.toml', '-r', '.')
        Invoke-Checked -Arguments @('export', '--quiet', '--locked', '--no-default-groups', '--no-emit-project', '--format', 'requirements-txt', '--output-file', 'reports/runtime-requirements.txt')
        Invoke-Checked -Arguments @('run', '--locked', '--all-groups', '--group', 'security', 'pip-audit', '-r', 'reports/runtime-requirements.txt', '--require-hashes', '--disable-pip')
        $scanner = Join-Path $workspace 'reports/tools/gitleaks.exe'
        if (-not (Test-Path -LiteralPath $scanner)) { throw 'Run scripts/install_tools.py before claiming Security verification.' }
        & $scanner git --redact --log-opts='--all' .
        if ($LASTEXITCODE -ne 0) { throw 'Secret history scan failed. Remediate exposed history; do not suppress findings.' }
    }
    if ($Mode -eq 'Release') {
        Invoke-Checked -Arguments @('build')
        throw 'Release gate remains open: clean-machine installation, signing, upgrade/rollback, and hosted verification require recorded evidence.'
    }
} finally {
    $env:QT_QPA_PLATFORM = $initialPlatform
    $env:UV_CACHE_DIR = $initialCache
    Set-Location -LiteralPath $initialDirectory
}
