@echo off
setlocal EnableExtensions
rem Reset ONLY the dedicated Research local/ChairPlay checkout to pinned pristine upstream.
rem Tracked local source changes in that checkout are intentionally discarded; untracked
rem user data (offline-mfi, pairings, local settings, logs) is NOT cleaned or deleted.
rem This does not update arbitrary Visual Studio/VS Code checkouts on the user's PC.
for %%I in ("%~dp0..") do set "PROJECT_ROOT=%%~fI"
set "SOURCE=%PROJECT_ROOT%\local\ChairPlay"
set "DEST=%SOURCE%\dist\ChairPlay"
set /p "REVISION="<"%PROJECT_ROOT%\UPSTREAM_REVISION.txt"

where git >nul 2>nul || (echo ERROR: Git not found in PATH. & exit /b 1)
where java >nul 2>nul || (echo ERROR: Java not found. Install JDK 17. & exit /b 1)
if not exist "%PROJECT_ROOT%\local" mkdir "%PROJECT_ROOT%\local"
if not exist "%SOURCE%\.git" (
    echo Cloning upstream feature/skoda_790...
    git clone --recurse-submodules --branch feature/skoda_790 https://github.com/zakklmv/ChairPlay.git "%SOURCE%"
    if errorlevel 1 exit /b 1
)
echo Fetching ChairPlay upstream and replacing the dedicated local source snapshot...
git -C "%SOURCE%" fetch origin feature/skoda_790
if errorlevel 1 exit /b 1
git -C "%SOURCE%" checkout --force --detach "%REVISION%"
if errorlevel 1 (echo ERROR: Pinned upstream commit unavailable; no build. & exit /b 1)
git -C "%SOURCE%" submodule update --init --recursive
if errorlevel 1 exit /b 1
echo Pinned upstream source:
git -C "%SOURCE%" log -1 --format="%%H %%cs %%s"
echo No Research Kotlin/TypeScript overrides are applied.

echo Applying reviewed live profile controls patch...
powershell -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%\scripts\apply-live-profile-patch.ps1" "%SOURCE%"
if errorlevel 1 exit /b 1

echo Applying reviewed Manual Setup and Scaling patch...
powershell -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%\scripts\apply-manual-scaling-patch.ps1" "%SOURCE%" "%PROJECT_ROOT%\scripts\patches\manual-scaling-v1.patch"
if errorlevel 1 exit /b 1

echo Setting test-only Vitest timeout for Windows...
powershell -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%\scripts\prepare-webui-tests.ps1" "%SOURCE%"
if errorlevel 1 exit /b 1

pushd "%SOURCE%" || exit /b 1
echo Testing upstream ChairPlay...
call gradlew.bat test --no-daemon --console=plain
if errorlevel 1 (popd & echo ERROR: Upstream tests failed. & exit /b 1)
echo Building upstream ChairPlay for Windows...
call gradlew.bat deploy --no-daemon --console=plain
if errorlevel 1 (popd & echo ERROR: Upstream Windows build failed. & exit /b 1)
popd
if not exist "%DEST%\ChairPlay.exe" set "DEST=%SOURCE%\build\jpackage\ChairPlay"
if not exist "%DEST%\ChairPlay.exe" (echo ERROR: ChairPlay.exe not produced. & exit /b 1)
if not exist "%DEST%\profiles" mkdir "%DEST%\profiles"
copy /Y "%PROJECT_ROOT%\profiles\mu1440-790-safeareas.json" "%DEST%\profiles\mu1440-790-safeareas.json" >nul
if errorlevel 1 exit /b 1
copy /Y "%PROJECT_ROOT%\profiles\mu1440-790-map-only.json" "%DEST%\profiles\mu1440-790-map-only.json" >nul
if errorlevel 1 exit /b 1
echo Installed: %DEST%
echo This script does not update a separate ChairPlay installation on the Desktop.
echo Start ChairPlay manually after backing up local pairing/MFi/config data if replacing another install.
start "" "%DEST%\ChairPlay.exe"
exit /b 0
