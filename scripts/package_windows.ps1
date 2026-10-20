param([ValidateSet('Exe','Msix','Both')][string]$Format='Both')
$ErrorActionPreference='Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$initialDirectory = Get-Location
try {
    Set-Location -LiteralPath $workspace
    $version = (& uv --cache-dir .uv-cache run --locked python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])").Trim()
    if ($LASTEXITCODE -ne 0 -or $version -notmatch '^\d+\.\d+\.\d+$') { throw 'Invalid package version.' }
    $output = Join-Path $workspace 'dist/installers'
    New-Item -ItemType Directory -Force $output | Out-Null
    if ($Format -in @('Exe','Both')) {
        $compiler = Join-Path $workspace 'reports/tools/inno-6.7.3/ISCC.exe'
        if (-not (Test-Path -LiteralPath $compiler)) { throw 'Run scripts/install_inno.ps1 first.' }
        & $compiler "/DAppVersion=$version" "/DPayloadDir=$workspace/dist/desktop/ColdMailer" "/DOutputPath=$output" packaging/windows/installer.iss *> reports/exe-packaging.log
        if ($LASTEXITCODE -ne 0) { throw 'EXE installer compilation failed.' }
    }
    if ($Format -in @('Msix','Both')) {
        $sdkRoot = Join-Path ${env:ProgramFiles(x86)} 'Windows Kits/10/bin'
        $makeappx = Join-Path $sdkRoot '10.0.26100.0/x64/makeappx.exe'
        if (-not (Test-Path -LiteralPath $makeappx)) { throw 'Windows SDK 10.0.26100.0 MakeAppx (x64) is required.' }
        $staging = Join-Path $workspace ('build/msix-' + [guid]::NewGuid().ToString('N'))
        & uv --cache-dir .uv-cache run --locked python -m scripts.prepare_msix --target $staging
        if ($LASTEXITCODE -ne 0) { throw 'MSIX payload preparation failed.' }
        & $makeappx pack /d $staging /p "$output/ColdMailer-$version-x64-unsigned.msix" /o *> reports/msix-packaging.log
        if ($LASTEXITCODE -ne 0) { throw 'MSIX schema/package validation failed.' }
    }
    $artifacts = Get-ChildItem -LiteralPath $output -File | Where-Object { $_.Extension -in @('.exe','.msix') }
    $artifacts | ForEach-Object { '{0}  {1}' -f (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant(),$_.Name } | Set-Content -LiteralPath (Join-Path $output 'SHA256SUMS.txt') -Encoding ascii
    Copy-Item -LiteralPath dist/desktop/development-manifest.json -Destination $output
    if (Test-Path reports/release-metadata.json) { Copy-Item -LiteralPath reports/release-metadata.json -Destination $output }
    Write-Output "Preview installers and checksums are in $output"
} finally { Set-Location -LiteralPath $initialDirectory }
