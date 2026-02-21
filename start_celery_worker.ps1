# PowerShell script to start Celery worker
# Usage: .\start_celery_worker.ps1 [worker_number]

param(
    [int]$WorkerNumber = 1,
    [string]$Queue = "pdf_processing"
)

Write-Host "`n🚀 Starting Celery Worker #$WorkerNumber" -ForegroundColor Green
Write-Host "Queue: $Queue" -ForegroundColor Cyan
Write-Host "="*60

# Get hostname
$hostname = $env:COMPUTERNAME

# Start worker
celery -A celery_app worker `
    --loglevel=info `
    --pool=solo `
    -Q $Queue `
    -n "worker$WorkerNumber@$hostname"
