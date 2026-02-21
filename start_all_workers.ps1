# PowerShell script to start all 5 workers at once
# Usage: .\start_all_workers.ps1

Write-Host ""
Write-Host "STARTING 5 CELERY WORKERS" -ForegroundColor Green
Write-Host "=========================" -ForegroundColor Green
Write-Host ""
Write-Host "This will open 5 PowerShell windows (one for each worker)" -ForegroundColor Cyan
Write-Host "Press Ctrl+C in each window to stop that worker" -ForegroundColor White
Write-Host ""

# Start Worker 1
Write-Host "Starting Worker 1..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:WORKER_NUM='1'; Write-Host 'Worker 1 Starting...' -ForegroundColor Green; python worker.py"

Start-Sleep -Seconds 2

# Start Worker 2
Write-Host "Starting Worker 2..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:WORKER_NUM='2'; Write-Host 'Worker 2 Starting...' -ForegroundColor Green; python worker.py"

Start-Sleep -Seconds 2

# Start Worker 3
Write-Host "Starting Worker 3..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:WORKER_NUM='3'; Write-Host 'Worker 3 Starting...' -ForegroundColor Green; python worker.py"

Start-Sleep -Seconds 2

# Start Worker 4
Write-Host "Starting Worker 4..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:WORKER_NUM='4'; Write-Host 'Worker 4 Starting...' -ForegroundColor Green; python worker.py"

Start-Sleep -Seconds 2

# Start Worker 5
Write-Host "Starting Worker 5..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:WORKER_NUM='5'; Write-Host 'Worker 5 Starting...' -ForegroundColor Green; python worker.py"

Write-Host ""
Write-Host "All 5 workers launched!" -ForegroundColor Green
Write-Host ""
Write-Host "Wait 10 seconds for workers to connect, then run test:" -ForegroundColor Cyan
Write-Host "   python test_workers_local.py" -ForegroundColor White
Write-Host ""
Write-Host "To monitor workers:" -ForegroundColor Yellow
Write-Host "   python monitor_workers.py" -ForegroundColor White
Write-Host ""
Write-Host "To stop all workers:" -ForegroundColor Red
Write-Host "   Press Ctrl+C in each worker window" -ForegroundColor White
Write-Host ""
