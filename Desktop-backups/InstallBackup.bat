@echo off
setlocal

rem - get/set vars to script locations
set Prog=BackupToFileEngine.bat
set SrcDir=%~dp0
set DstDir=C:\Epiphany\
set PasswordParm=%1
set UsernameParm=%2

if "%PasswordParm%"=="" set PasswordParm=*
if "%UsernameParm%"=="" set UsernameParm=%USERNAME%

echo Copy the backup script "%Prog%" to the "%DstDir%" folder
copy /a /y %SrcDir%%Prog% %DstDir%%Prog%
IF %ERRORLEVEL% NEQ 0 goto :FailCleanup

echo .
echo Add three scheduled tasks to the System
rem minutes needs to be random (note: first call is not that random)
SET /A minute=%RANDOM%
SET /A minute=%RANDOM% %% 60
set minute=00%minute%
set minute=%minute:~-2%
rem - minute is now random from 00 to 59 (always 2 digits)

rem - Add the three tasks to the system.  Every Thur at 10:00 AM (forground) - If not media pc,
rem - one daily at 2:xx PM (background), and one nightly at 3:xx AM (background).
rem - where xx is the random minute (do not run backups on all PCs at the same time).

set UserPassOpt=/RU %UsernameParm% /RP "%PasswordParm%"

SchTasks /Create /SC DAILY /F /TN "Epiphany Backup Daily" /TR "cmd /C %DstDir%%Prog% /nowarn" /ST 14:%minute% %UserPassOpt%
IF %ERRORLEVEL% NEQ 0 goto :FailCleanup
SchTasks /Create /SC DAILY /F /TN "Epiphany Backup Nightly" /TR "cmd /C %DstDir%%Prog% /nowarn" /ST 03:%minute% %UserPassOpt%
IF %ERRORLEVEL% NEQ 0 goto :FailCleanup
if /I "%UsernameParm%"=="windsx" goto :SkipMediaCreate
SchTasks /Create /SC WEEKLY /D THU /F /TN "Epiphany Backup Weekly" /TR "cmd /C %DstDir%%Prog%" /ST 10:00
IF %ERRORLEVEL% NEQ 0 goto :FailCleanup
:SkipMediaCreate

SchTasks /Query /TN "Epiphany Backup Daily"
SchTasks /Query /TN "Epiphany Backup Nightly"
if /I NOT "%UsernameParm%"=="windsx" SchTasks /Query /TN "Epiphany Backup Weekly"

echo .
echo Install Complete
goto :Done

:FailCleanup
pause
echo .
echo Cleanup script and scheduled tasks (Ok if these cleanup commands fail)
del /F %DstDir%%Prog%
verify >nul
SchTasks /Delete /F /TN "Epiphany Backup Daily"
SchTasks /Delete /F /TN "Epiphany Backup Nightly"
SchTasks /Delete /F /TN "Epiphany Backup Weekly"

echo Cleanup Complete
goto :Done

:Done
pause
endlocal
