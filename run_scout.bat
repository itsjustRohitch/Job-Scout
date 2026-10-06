@echo off
cd /d "C:\Users\rohit\Desktop\job_scout"
set PYTHONUTF8=1
call "venv\Scripts\activate.bat"
python main.py >> scout_log.txt 2>&1