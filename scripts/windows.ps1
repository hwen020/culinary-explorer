param([ValidateSet('start','stop')][string]$Action = 'start')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path $PSScriptRoot -Parent)
$state = Join-Path $PWD '.local-run'
$ready = Join-Path $state 'ready'
$owner = Join-Path $state 'owner'
$stop = Join-Path $state 'stop'
$url = 'http://localhost:5173'

if ($Action -eq 'stop') {
    if (!(Test-Path $owner)) { Write-Host 'Culinary Explorer is stopped.'; exit 0 }
    New-Item -ItemType File -Path $stop -Force | Out-Null
    for ($i=0; $i -lt 100 -and (Test-Path $owner); $i++) { Start-Sleep -Milliseconds 250 }
    if (Test-Path $owner) { throw 'Shutdown did not finish. See .local-run/supervisor.err.' }
    Write-Host 'Culinary Explorer stopped.'
    exit 0
}

if (Test-Path $owner) {
    $existing = Get-Process -Id ([int](Get-Content -LiteralPath $owner)) -ErrorAction SilentlyContinue
    if ($existing -and (Test-Path $ready)) { Write-Host $url; exit 0 }
    if ($existing) { throw 'Culinary Explorer is starting or stopping.' }
}

$node = Get-Command node.exe
$nodeVersion = [version]((& $node.Source --version).TrimStart('v'))
if ($nodeVersion.Major -lt 20) { throw 'Install Node.js 20 or later.' }
$null = Get-Command npm.cmd
$python = @('.venv\Scripts\python.exe','.venv312\Scripts\python.exe') | Where-Object {
    (Test-Path $_) -and (& $_ -c 'import sys; print(sys.version_info[:2] == (3, 12))') -eq 'True'
} | Select-Object -First 1
if (!$python) {
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if (!$launcher) { throw 'Install Python 3.12 with the Windows Python launcher.' }
    & $launcher.Source -3.12 -m venv .venv312
    if ($LASTEXITCODE) { throw 'Could not create a Python 3.12 environment.' }
    $python = '.venv312\Scripts\python.exe'
}
$python = (Resolve-Path -LiteralPath $python).Path
New-Item -ItemType Directory -Path $state -Force | Out-Null
if (!(Test-Path .env)) { Copy-Item -LiteralPath .env.example -Destination .env }

$pythonStamp = Join-Path $state 'python-dependencies'
$pythonDigest = (Get-FileHash -LiteralPath requirements-lock.txt).Hash + ' ' + $python
if (!(Test-Path $pythonStamp) -or (Get-Content -LiteralPath $pythonStamp) -ne $pythonDigest) {
    & $python -m pip --disable-pip-version-check install -q -r requirements-lock.txt
    if ($LASTEXITCODE) { throw 'Python dependency installation failed.' }
    Set-Content -LiteralPath $pythonStamp -Value $pythonDigest
}
$nodeStamp = Join-Path $state 'node-dependencies'
$nodeDigest = (Get-FileHash -LiteralPath package-lock.json).Hash
if (!(Test-Path 'node_modules/vite/bin/vite.js') -or !(Test-Path $nodeStamp) -or
    (Get-Content -LiteralPath $nodeStamp) -ne $nodeDigest) {
    & npm.cmd ci --no-audit --no-fund
    if ($LASTEXITCODE) { throw 'Node dependency installation failed.' }
    Set-Content -LiteralPath $nodeStamp -Value $nodeDigest
}
$process = Start-Process -FilePath $python -ArgumentList '-m','backend.local_services' -WorkingDirectory $PWD.Path -WindowStyle Hidden -PassThru
for ($i=0; $i -lt 120; $i++) {
    if ($process.HasExited) { throw 'Startup failed. See .local-run/supervisor.err and service logs.' }
    if (Test-Path $ready) { Write-Host "Culinary Explorer $url"; exit 0 }
    Start-Sleep -Milliseconds 250
}
if ((Test-Path $owner) -and ([int](Get-Content -LiteralPath $owner) -eq $process.Id)) {
    New-Item -ItemType File -Path $stop -Force | Out-Null
}
throw 'Startup timed out. See .local-run service logs.'
