@echo off
REM Single test runner — Challenge 5 (The Cut)
REM Runs both test suites and reports combined result.
REM Both must be green before any extraction work is considered done.

SET PASS=0
SET FAIL=0
SET ROOT=%~dp0

echo.
echo ============================================================
echo  Suite 1: Monolith characterization tests (Java / JUnit)
echo  Spring Music — pins current behavior before modernization
echo ============================================================
cd /d "%ROOT%spring-music-master"

powershell -Command "Remove-Item -Path 'build\test-results\test\binary' -Recurse -Force -ErrorAction SilentlyContinue" 2>nul

call gradlew.bat test --tests "org.cloudfoundry.samples.music.AlbumControllerCharacterizationTest" --no-daemon -q
IF %ERRORLEVEL% EQU 0 (
    echo [PASS] Monolith characterization suite
    SET /A PASS+=1
) ELSE (
    echo [FAIL] Monolith characterization suite
    SET /A FAIL+=1
)

echo.
echo ============================================================
echo  Suite 2: Album Catalog Service contract tests (Python / pytest)
echo  New service — verifies clean API contract and fixes
echo ============================================================
cd /d "%ROOT%album-catalog-service"

python -m pytest tests/test_contract.py -v --tb=short
IF %ERRORLEVEL% EQU 0 (
    echo [PASS] Album Catalog Service contract suite
    SET /A PASS+=1
) ELSE (
    echo [FAIL] Album Catalog Service contract suite
    SET /A FAIL+=1
)

echo.
echo ============================================================
echo  Result: %PASS% suite(s) passed, %FAIL% suite(s) failed
echo ============================================================
IF %FAIL% EQU 0 (
    echo  ALL GREEN — The Cut is verified.
    exit /b 0
) ELSE (
    echo  FAILING — do not proceed with further extraction.
    exit /b 1
)
