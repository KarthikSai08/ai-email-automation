[windows]
set shell := ["pwsh", "-NoLogo", "-Command"]

default: lint

# Create .env from the template if missing
env:
    if (!(Test-Path .env)) { Copy-Item .env.example .env; Write-Host "Created .env from .env.example" } else { Write-Host ".env already exists" }

# Install the package in editable mode
install:
    pip install -e .

# Start the Gmail watch (enables push notifications)
watch:
    gmail-watch

# Start the Pub/Sub listener (long-running process)
listen:
    gmail-listener

# Start the FastAPI server (long-running process)
api:
    gmail-api

# Run the test suite
test:
    $env:PYTHONPATH = "src"
    python -m pytest tests -q

# Lint the codebase
lint:
    ruff check .

# Auto-fix all fixable lint issues
fix:
    ruff check . --fix

# Format the codebase
fmt:
    ruff format .

# Check formatting without changing files
fmt-check:
    ruff format --check .

# Kill any running listener process
stop:
    Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object { $_.CommandLine -match 'gmail_access|pubsub_listener|gmail-listener' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
    Write-Host "Stopped any running listener."
