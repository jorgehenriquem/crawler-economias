@echo off
REM Atalho para o me-crawler no WSL
REM Uso: run.bat sync
REM      run.bat dashboard --open
REM      run.bat login
wsl -d Ubuntu -e bash -c "source ~/.venvs/me-crawler/bin/activate && cd /mnt/c/Users/jorge/Documents/projetos/crawler-economias && me-crawler %*"
