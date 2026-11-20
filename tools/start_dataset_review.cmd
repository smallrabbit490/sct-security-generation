@echo off
cd /d "%~dp0.."
python tools\dataset_review.py --open
if errorlevel 1 pause
