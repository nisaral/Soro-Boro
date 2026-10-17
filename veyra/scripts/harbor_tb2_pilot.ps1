# Requires Python 3.12 + Docker Desktop running (admin to start com.docker.service).
$ErrorActionPreference = "Stop"
$py = "C:\Users\nisar\AppData\Local\Programs\Python\Python312\python.exe"
$env:Path = "C:\Users\nisar\AppData\Local\Programs\Python\Python312;C:\Users\nisar\AppData\Local\Programs\Python\Python312\Scripts;" + $env:Path

# Load .env if present
$dotenv = Join-Path $PSScriptRoot "..\.env"
if (Test-Path $dotenv) {
    Get-Content $dotenv | ForEach-Object {
        if ($_ -and -not $_.StartsWith("#") -and $_.Contains("=")) {
            $parts = $_.Split("=", 2)
            [Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim(), "Process")
        }
    }
}

if (-not $env:OPENAI_API_KEY -and $env:ODYSSEY_API_KEY) { $env:OPENAI_API_KEY = $env:ODYSSEY_API_KEY }
if (-not $env:OPENAI_API_KEY) { throw "Set OPENAI_API_KEY or ODYSSEY_API_KEY in environment or .env" }
if (-not $env:OPENAI_BASE_URL) { $env:OPENAI_BASE_URL = "https://odysseyapi.tech/v1" }

$out = Join-Path $PSScriptRoot "..\out\harbor_tb2_pilot"
New-Item -ItemType Directory -Force -Path $out | Out-Null
# 5-task cost pilot (plan 4g). Raise -l to 20 after Docker works.
harbor run -d terminal-bench@2.0 -a terminus-2 -m openai/openai/gpt-4o -l 5 -n 1 -k 1 -o $out -y
