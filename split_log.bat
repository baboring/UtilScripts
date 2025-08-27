@echo off
setlocal

:: Basic settings
set SCRIPT=split_log/split_log.py
::set DEFAULT_LOG=input.log
set DEFAULT_LOG=Sources/Filtered.log
set DEFAULT_KEYWORD=split_log/keywords.txt
set OUTPUT_DIR=Results

echo =======================================
echo   Log Splitting Script Executor
echo =======================================
set /p LOGFILE="Log file path (default: %DEFAULT_LOG%) : "
if "%LOGFILE%"=="" set LOGFILE=%DEFAULT_LOG%

echo Keyword input methods:
echo  - Enter directly separated by commas (e.g., ERROR,WARN,CRITICAL)
echo  - Enter the filename containing keywords (e.g., keywords.txt)
set /p KEYWORD="Keywords to search (file or direct input, default: %DEFAULT_KEYWORD%) : "
if "%KEYWORD%"=="" set KEYWORD=%DEFAULT_KEYWORD%

set /p OUTDIR="Output folder name (default: %OUTPUT_DIR%) : "
if "%OUTDIR%"=="" set OUTDIR=%OUTPUT_DIR%

echo Running...
python "%SCRIPT%" "%LOGFILE%" "%KEYWORD%" "%OUTDIR%"

pause