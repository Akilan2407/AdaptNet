$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$python = if (Test-Path $venvPython) {
    $venvPython
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    (Get-Command python).Source
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    (Get-Command py).Source
} else {
    $null
}

if (-not $python) {
    throw "Python was not found. Install Python 3.10+ and add it to PATH."
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "npm was not found. Install Node.js 18+ and add it to PATH."
}

function Test-PortInUse([int] $port) {
    return $null -ne (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}

$backendPort = 5001
$frontendPort = 3000
$backendProcess = $null
$frontendProcess = $null

try {
    if (Test-PortInUse $backendPort) {
        Write-Host "[+] Backend is already running on port $backendPort"
    } else {
        Write-Host "[*] Starting Flask backend on port $backendPort..."
        $previousPort = $env:PORT
        $env:PORT = "$backendPort"
        $pythonArguments = if ([IO.Path]::GetFileName($python) -ieq "py.exe") {
            @("-3", "backend\app.py")
        } else {
            @("backend\app.py")
        }
        $backendProcess = Start-Process -FilePath $python `
            -ArgumentList $pythonArguments `
            -WorkingDirectory $projectRoot `
            -PassThru
        if ($null -eq $previousPort) { Remove-Item Env:PORT } else { $env:PORT = $previousPort }
    }

    if (Test-PortInUse $frontendPort) {
        Write-Host "[+] Frontend is already running on port $frontendPort"
    } else {
        Write-Host "[*] Starting React frontend on port $frontendPort..."
        $viteScript = Join-Path $projectRoot "frontend\node_modules\vite\bin\vite.js"
        $frontendProcess = Start-Process -FilePath "node.exe" `
            -ArgumentList $viteScript, "--port", "$frontendPort" `
            -WorkingDirectory (Join-Path $projectRoot "frontend") `
            -PassThru
    }

    Write-Host ""
    Write-Host "System online"
    Write-Host "  Frontend : http://localhost:$frontendPort"
    Write-Host "  Backend  : http://localhost:$backendPort/api"
    Write-Host "  Health   : http://localhost:$backendPort/api/health"
    Write-Host ""
    Write-Host "Press Ctrl+C to stop this launcher."
    while ($true) {
        Start-Sleep -Seconds 1
        if ($backendProcess -and $backendProcess.HasExited) {
            throw "The backend process exited unexpectedly."
        }
        if ($frontendProcess -and $frontendProcess.HasExited) {
            throw "The frontend process exited unexpectedly."
        }
    }
} finally {
    foreach ($process in @($backendProcess, $frontendProcess)) {
        if ($process -and -not $process.HasExited) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        }
    }
}
