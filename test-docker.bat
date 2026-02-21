@echo off
REM ========================================
REM ProfessorAI Docker Testing Script
REM Stage 1: Containerization
REM ========================================

echo.
echo ================================
echo  ProfessorAI Docker Test
echo ================================
echo.

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not running!
    echo Please start Docker Desktop and try again.
    echo.
    pause
    exit /b 1
)

echo [OK] Docker is running...
echo.

REM Check if .env exists
if not exist .env (
    echo [ERROR] .env file not found!
    echo Please create .env file with your API keys.
    echo.
    pause
    exit /b 1
)

echo [OK] .env file found...
echo.

echo Choose an option:
echo 1. Build Docker image only
echo 2. Build and run with Docker Compose
echo 3. View logs
echo 4. Stop and cleanup
echo 5. Full rebuild (no cache)
echo.

set /p choice="Enter your choice (1-5): "

if "%choice%"=="1" goto build
if "%choice%"=="2" goto compose_up
if "%choice%"=="3" goto logs
if "%choice%"=="4" goto cleanup
if "%choice%"=="5" goto rebuild
goto invalid

:build
echo.
echo Building Docker image...
echo.
docker build -t profai:latest .
if errorlevel 1 (
    echo.
    echo [ERROR] Build failed! Check the output above.
    pause
    exit /b 1
)
echo.
echo [SUCCESS] Image built successfully!
echo.
echo Next steps:
echo - Run: docker-compose up
echo - Or run this script and choose option 2
echo.
pause
exit /b 0

:compose_up
echo.
echo Starting ProfessorAI with Docker Compose...
echo.
echo This will:
echo - Build the image if not exists
echo - Start the container
echo - Expose ports 5001 (API) and 8765 (WebSocket)
echo.
docker-compose up --build
pause
exit /b 0

:logs
echo.
echo Showing logs...
echo Press Ctrl+C to exit
echo.
docker-compose logs -f profai
pause
exit /b 0

:cleanup
echo.
echo Stopping and removing containers...
docker-compose down
echo.
echo [SUCCESS] Cleanup complete!
echo.
pause
exit /b 0

:rebuild
echo.
echo Rebuilding from scratch (no cache)...
echo This will take longer but ensures a clean build.
echo.
docker-compose build --no-cache
if errorlevel 1 (
    echo.
    echo [ERROR] Build failed! Check the output above.
    pause
    exit /b 1
)
echo.
echo [SUCCESS] Rebuild complete!
echo.
echo Start the container with: docker-compose up
echo Or run this script and choose option 2
echo.
pause
exit /b 0

:invalid
echo.
echo Invalid choice!
echo.
pause
exit /b 1
