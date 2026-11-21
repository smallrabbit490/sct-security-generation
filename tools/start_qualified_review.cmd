@echo off
cd /d "%~dp0.."
python tools\dataset_review.py --review-dir data\audit_release_20261118\qualified_risk_review_20261121 --out translation_work\diagnostics\20261121\qualified_review_ui\index.html --open
if errorlevel 1 pause
