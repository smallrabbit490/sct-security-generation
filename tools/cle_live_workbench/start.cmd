@echo off
cd /d "%~dp0..\.."
translation_work\temp\cle_memory_q_env\Scripts\python.exe -B -X utf8 -m tools.cle_live_workbench.app start
pause
