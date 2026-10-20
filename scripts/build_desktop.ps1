$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$initialDirectory = Get-Location
$initialCache = $env:UV_CACHE_DIR
try {
    Set-Location -LiteralPath $workspace
    $env:UV_CACHE_DIR = Join-Path $workspace '.uv-cache'
    & uv run --locked --group build pyinstaller --noconfirm --windowed --name ColdMailer --distpath dist/desktop --workpath build/desktop --specpath build --paths src --collect-data cold_mailer.ui --hidden-import keyring.backends.Windows --log-level WARN src/cold_mailer/ui/__main__.py
    if ($LASTEXITCODE -ne 0) { throw 'Desktop build failed.' }
    & uv run --locked python scripts/desktop_manifest.py
    if ($LASTEXITCODE -ne 0) { throw 'Desktop manifest generation failed.' }
} finally {
    $env:UV_CACHE_DIR = $initialCache
    Set-Location -LiteralPath $initialDirectory
}
