@echo off
setlocal EnableDelayedExpansion

for /f "usebackq tokens=1,* delims==" %%A in ("pg_backup_config.env") do (
    set %%A=%%B
)

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%..\.."

set "IMAGES_SOURCE=%PROJECT_ROOT%\%IMAGES_PATH%"

set TIMESTAMP=%DATE:~10,4%-%DATE:~4,2%-%DATE:~7,2%_%TIME:~0,2%%TIME:~3,2%
set "DB_FILENAME=%BACKUP_DIR%\%DBNAME%_%TIMESTAMP%.backup"
set "IMAGES_BACKUP_DIR=%BACKUP_DIR%\images_%TIMESTAMP%"
set "LOGFILE=%BACKUP_DIR%\backup_log.txt"

:: Check if backup directory exists, create if needed
if not exist "%BACKUP_DIR%" (
    echo [%DATE% %TIME%] Creating backup directory "%BACKUP_DIR%" >> "%~dp0backup_log.txt"
    mkdir "%BACKUP_DIR%"
    if !ERRORLEVEL! NEQ 0 (
        echo [%DATE% %TIME%] ERROR: Cannot create backup directory "%BACKUP_DIR%". >> "%~dp0backup_log.txt"
        goto :eof
    )
)

:: Perform database backup using dynamic pg_dump path
set "PG_DUMP=%PG_BIN%\pg_dump.exe"

if not exist "%PG_DUMP%" (
    echo [%DATE% %TIME%] ERROR: pg_dump not found at "%PG_DUMP%". >> "%LOGFILE%"
    goto :eof
)

echo [%DATE% %TIME%] Starting database backup for %DBNAME% >> "%LOGFILE%"
"%PG_DUMP%" -U %PGUSER% -h %PGHOST% -p %PGPORT% -F c -f "%DB_FILENAME%" %DBNAME%
if %ERRORLEVEL% NEQ 0 (
    echo [%DATE% %TIME%] ERROR: Database backup failed with code %ERRORLEVEL% >> "%LOGFILE%"
    goto :eof
) else (
    echo [%DATE% %TIME%] Database backup successful: %DB_FILENAME% >> "%LOGFILE%"
)

:: Backup images if directory exists
if exist "%IMAGES_SOURCE%" (
    echo [%DATE% %TIME%] Starting images backup from %IMAGES_SOURCE% >> "%LOGFILE%"
    
    :: Create images backup directory
    if not exist "%IMAGES_BACKUP_DIR%" mkdir "%IMAGES_BACKUP_DIR%"
    
    :: Copy all files from images directory
    xcopy "%IMAGES_SOURCE%\*" "%IMAGES_BACKUP_DIR%\" /Y /Q
    if !ERRORLEVEL! EQU 0 (
        echo [%DATE% %TIME%] Images backup successful: %IMAGES_BACKUP_DIR% >> "%LOGFILE%"
    ) else (
        echo [%DATE% %TIME%] WARNING: Images backup had issues with code !ERRORLEVEL! >> "%LOGFILE%"
    )
) else (
    echo [%DATE% %TIME%] INFO: Images directory "%IMAGES_SOURCE%" not found, skipping images backup >> "%LOGFILE%"
)

:: Cleanup old backups - keep only 3 most recent
echo [%DATE% %TIME%] Cleaning up old backups (keeping 3 most recent) >> "%LOGFILE%"

:: Count database backup files and delete oldest ones if more than 3
set count=0
for /f "delims=" %%f in ('dir /b /o-d "%BACKUP_DIR%\%DBNAME%_*.backup" 2^>nul') do (
    set /a count+=1
    if !count! GTR 3 (
        echo [%DATE% %TIME%] Deleting old database backup: %%f >> "%LOGFILE%"
        del "%BACKUP_DIR%\%%f"
    )
)

:: Count image backup directories and delete oldest ones if more than 3
set count=0
for /f "delims=" %%d in ('dir /b /o-d /ad "%BACKUP_DIR%\images_*" 2^>nul') do (
    set /a count+=1
    if !count! GTR 3 (
        echo [%DATE% %TIME%] Deleting old images backup: %%d >> "%LOGFILE%"
        rmdir /s /q "%BACKUP_DIR%\%%d"
    )
)

echo [%DATE% %TIME%] Backup completed successfully >> "%LOGFILE%"
echo [%DATE% %TIME%] Database backup: %DB_FILENAME% >> "%LOGFILE%"
echo [%DATE% %TIME%] Images backup: %IMAGES_BACKUP_DIR% >> "%LOGFILE%"

endlocal