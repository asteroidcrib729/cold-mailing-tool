$ErrorActionPreference='Stop'
function Invoke-SmokeProcess {
    param([string]$Executable,[string[]]$Arguments)
    $process = Start-Process -FilePath $Executable -ArgumentList $Arguments -WindowStyle Hidden -PassThru
    if (-not $process.WaitForExit(60000)) {
        Stop-Process -Id $process.Id -Force
        throw 'The isolated installer smoke process exceeded 60 seconds.'
    }
    if ($process.ExitCode -ne 0) { throw "Isolated smoke process failed with exit code $($process.ExitCode)." }
}
$workspace = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$installation = [IO.Path]::GetFullPath((Join-Path $workspace 'reports/installer-smoke-app'))
$profile = Join-Path $workspace 'reports/installer-smoke-profile'
if (-not $installation.StartsWith($workspace + [IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe smoke installation destination.' }
if (Test-Path -LiteralPath $installation) { throw 'Choose a fresh smoke installation directory.' }
$installer = Get-ChildItem -LiteralPath (Join-Path $workspace 'dist/installers') -Filter '*-setup.exe' | Select-Object -First 1
if (-not $installer) { throw 'EXE installer not found.' }
$installArguments = @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/CURRENTUSER',"/DIR=`"$installation`"")
foreach ($pass in 1,2) {
    Invoke-SmokeProcess -Executable $installer.FullName -Arguments $installArguments
    $app = Join-Path $installation 'ColdMailer.exe'
    Invoke-SmokeProcess -Executable $app -Arguments @('--smoke-test','--data-dir',"`"$profile`"")
    $database = Join-Path $profile 'campaigns.sqlite3'
    if (-not (Test-Path -LiteralPath $database)) { throw 'Installed application did not persist its profile.' }
    if ($pass -eq 1) { $before = (Get-FileHash -LiteralPath $database -Algorithm SHA256).Hash }
}
Invoke-SmokeProcess -Executable (Join-Path $installation 'unins000.exe') -Arguments @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART')
if ((Get-FileHash -LiteralPath $database -Algorithm SHA256).Hash -ne $before) { throw 'Profile changed during reinstall/uninstall smoke.' }
$environment = if ($env:GITHUB_ACTIONS -eq 'true') {'hosted_runner'} else {'local_windows'}
@{install=$true;reinstall=$true;uninstall=$true;profile_preserved=$true;environment=$environment;msix_install='Not tested: unsigned preview requires an explicit trust/signing policy';clean_machine='Isolated smoke only; clean user VM remains required'} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $workspace 'reports/installer-smoke.json')
