@echo off
cd /d "%~dp0"
set STREAMLIT_CONFIG_DIR=%~dp0.streamlit
set STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
backend\.venv\Scripts\streamlit.exe run streamlit_app.py %*
