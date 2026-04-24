@echo off
REM Cutover rehearsal runner — Challenge 8 (The Weekend)
REM Executes runbook steps against a real live instance.
REM Exits 0 = GO, exits 1 = NO-GO.

SET ROOT=%~dp0
python "%ROOT%rehearse.py"
