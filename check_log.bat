@echo off
REM ==========================================
REM Log Check Execution Batch File
REM Usage:
REM   run_check.bat [log_file] [check_file]
REM If parameters are not provided, default values are used:
REM   log_file = input_file.log
REM   check_file = checklist.txt
REM The result file will be automatically saved as result_<logfile>_<timestamp>.txt
REM ==========================================

set LOGFILE=%1
set CHECKFILE=%2

REM Apply default values
if "%LOGFILE%"=="" set LOGFILE=sources/input_file.log
if "%CHECKFILE%"=="" set CHECKFILE=check_log/checklist.txt

echo [INFO] script file: %LOGFILE%
echo [INFO] check file: %CHECKFILE%
echo.

REM Run Python script
python check_log/check_log.py "%LOGFILE%" "%CHECKFILE%"
pause
