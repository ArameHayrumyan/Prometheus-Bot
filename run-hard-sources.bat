@echo off
REM Double-click to scrape the sources blocked from the cloud (GitHub Actions):
REM Reddit, LinkedIn guest, and Cloudflare-protected web pages. Runs from your
REM home IP, which those sites allow. Results land in the bot's /queue.
REM
REM Requires: Docker Desktop running, and a filled .env next to this file.

cd /d "%~dp0"

echo ==================================================================
echo   Moonin - local scrape for cloud-blocked sources
echo   (Reddit + LinkedIn + web pages, from your residential IP)
echo ==================================================================
echo.

where docker >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Docker was not found. Start Docker Desktop and try again.
  echo.
  pause
  exit /b 1
)

echo [1/2] Building the image so it has the latest code...
echo       (fast after the first time - Docker caches the heavy layers)
echo.
docker compose build bot
if errorlevel 1 (
  echo.
  echo [ERROR] Build failed. Scroll up for the reason.
  echo.
  pause
  exit /b 1
)

echo.
echo [2/2] Starting scrape... this can take 10-20 minutes ^(polite per-site spacing^).
echo       You can minimize this window; a summary DM arrives in the bot when done.
echo.

docker compose run --rm bot python -m app.scraper_cli hard

echo.
echo ------------------------------------------------------------------
echo Finished. Open your bot and check /queue for new items.
echo ------------------------------------------------------------------
echo.
pause
