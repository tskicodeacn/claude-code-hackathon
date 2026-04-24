@echo off
REM Scorecard runner — Challenge 7 (The Scorecard)
REM Runs seam classification eval + behavior preservation check.
REM Pass --dry-run to skip Anthropic API calls (uses ground-truth stubs).
REM Pass --skip-behavior to skip the Java+Python test suites.
REM
REM Requirements:
REM   ANTHROPIC_API_KEY env var (unless --dry-run)
REM   pip install anthropic

SET ROOT=%~dp0

echo.
echo ============================================================
echo  Challenge 7 — The Scorecard
echo  Seam classification eval + behavior preservation check
echo ============================================================

python "%ROOT%eval.py" %*

IF %ERRORLEVEL% EQU 0 (
    echo.
    echo  [PASS] Scorecard complete.
    exit /b 0
) ELSE (
    echo.
    echo  [FAIL] Scorecard reported failures — see output above.
    exit /b 1
)
