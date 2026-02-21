# Setup Redis Environment Variables for Docker Compose
# Run this script to create/update your .env file with Redis Labs credentials

$envFile = ".env"
$exampleFile = ".env.example"

Write-Host "=================================" -ForegroundColor Cyan
Write-Host "Redis Labs Environment Setup" -ForegroundColor Cyan
Write-Host "=================================" -ForegroundColor Cyan
Write-Host ""

# Redis Labs Cloud Credentials
$REDIS_URL = "rediss://default:EcS70NONbhkMOEGeDpiQyLJUTtyNQqI4@redis-10925.crce206.ap-south-1-1.ec2.cloud.redislabs.com:10925"
$REDIS_PASSWORD = "EcS70NONbhkMOEGeDpiQyLJUTtyNQqI4"

# Check if .env exists
if (Test-Path $envFile) {
    Write-Host "[INFO] .env file already exists" -ForegroundColor Yellow
    $response = Read-Host "Do you want to update Redis credentials? (y/n)"
    if ($response -ne 'y') {
        Write-Host "[SKIP] Keeping existing .env file" -ForegroundColor Yellow
        exit 0
    }
    
    # Read existing .env
    $content = Get-Content $envFile -Raw
    
    # Update or add Redis variables
    if ($content -match "REDIS_URL=") {
        $content = $content -replace "REDIS_URL=.*", "REDIS_URL=$REDIS_URL"
        Write-Host "[UPDATE] Updated REDIS_URL" -ForegroundColor Green
    } else {
        $content += "`nREDIS_URL=$REDIS_URL"
        Write-Host "[ADD] Added REDIS_URL" -ForegroundColor Green
    }
    
    if ($content -match "REDIS_PASSWORD=") {
        $content = $content -replace "REDIS_PASSWORD=.*", "REDIS_PASSWORD=$REDIS_PASSWORD"
        Write-Host "[UPDATE] Updated REDIS_PASSWORD" -ForegroundColor Green
    } else {
        $content += "`nREDIS_PASSWORD=$REDIS_PASSWORD"
        Write-Host "[ADD] Added REDIS_PASSWORD" -ForegroundColor Green
    }
    
    # Save updated content
    $content | Set-Content $envFile -NoNewline
    
} else {
    Write-Host "[INFO] Creating new .env file from .env.example" -ForegroundColor Cyan
    
    if (Test-Path $exampleFile) {
        Copy-Item $exampleFile $envFile
        Write-Host "[SUCCESS] Copied .env.example to .env" -ForegroundColor Green
    } else {
        # Create minimal .env file
        @"
# Redis Labs Cloud Configuration
REDIS_URL=$REDIS_URL
REDIS_PASSWORD=$REDIS_PASSWORD

# Server Configuration
HOST=0.0.0.0
PORT=5001
DEBUG=False

# Database Configuration
USE_DATABASE=False

# Vector Store
USE_CHROMA_CLOUD=False

# API Keys (REPLACE WITH YOUR ACTUAL KEYS)
OPENAI_API_KEY=your-openai-api-key-here
SARVAM_API_KEY=your-sarvam-api-key-here
GROQ_API_KEY=your-groq-api-key-here
ELEVENLABS_API_KEY=your-elevenlabs-api-key-here

# Audio Provider Selection
AUDIO_STT_PROVIDER=deepgram
AUDIO_TTS_PROVIDER=elevenlabs
"@ | Set-Content $envFile
        Write-Host "[SUCCESS] Created new .env file" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "=================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "=================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Redis Configuration:" -ForegroundColor Cyan
Write-Host "  Host: redis-10925.crce206.ap-south-1-1.ec2.cloud.redislabs.com"
Write-Host "  Port: 10925"
Write-Host "  SSL: Enabled"
Write-Host ""
Write-Host "[NEXT STEPS]" -ForegroundColor Yellow
Write-Host "1. Edit .env and add your other API keys (OpenAI, etc.)"
Write-Host "2. Run: docker-compose -f docker-compose-production.yml up -d --build"
Write-Host ""
