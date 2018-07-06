@echo off
setlocal

rem - get/set vars to script locations
set Prog=backup-Jordan.vbs
set SrcDir=%~dp0
set DstDir=C:\Epiphany\

echo Copy the backup script "%Prog%" to the "%DstDir%" folder
copy /a /y %SrcDir%%Prog% %DstDir%%Prog%
IF %ERRORLEVEL% NEQ 0 goto :FailCleanup

echo .
echo Add two scheduled tasks to the System
rem minutes needs to be random (note: first call is not that random)
SET /A minute=%RANDOM%
SET /A minute=%RANDOM% %% 60
set minute=00%minute%
set minute=%minute:~-2%
rem - minute is now random from 00 to 59 (always 2 digits)

rem set UserPass=/RU windsx /RP "xxxxxxxx"
set UserPass=/RU jordan

rem - Add the two tasks to the system.  One daily at 2:xx PM (background) and one nightly at 3:xx AM (background).
rem - where xx is the random minute (do not run backups on all PCs at the same time).

SchTasks /Create /SC DAILY /F /TN "Jordan Backup Daily" /TR "%DstDir%%Prog% /nowarn" /ST 14:%minute% %UserPass%
IF %ERRORLEVEL% NEQ 0 goto :FailCleanup
SchTasks /Create /SC DAILY /F /TN "Jordan Backup Nightly" /TR "%DstDir%%Prog% /nowarn" /ST 03:%minute% %UserPass%
IF %ERRORLEVEL% NEQ 0 goto :FailCleanup
SchTasks /Create /SC WEEKLY /D THU /F /TN "Jordan Backup Weekly" /TR "cmd /C %DstDir%%Prog%" /ST 10:00
IF %ERRORLEVEL% NEQ 0 goto :FailCleanup

SchTasks /Query /TN "Jordan Backup Daily"
SchTasks /Query /TN "Jordan Backup Nightly"
SchTasks /Query /TN "Jordan Backup Weekly"

echo .
echo Install Complete
goto :Done

:FailCleanup
pause
echo .
echo Cleanup script and scheduled tasks (Ok if these cleanup commands fail)
del /F %DstDir%%Prog%
verify >nul
SchTasks /Delete /F /TN "Jordan Backup Daily"
SchTasks /Delete /F /TN "Jordan Backup Nightly"
SchTasks /Delete /F /TN "Jordan Backup Weekly"

echo Cleanup Complete
goto :Done

:Done

rem SchTasks /Change /TN "Jordan Backup Daily" /DISABLE
rem SchTasks /Change /TN "Jordan Backup Nightly" /DISABLE
rem SchTasks /Change /TN "Jordan Backup Weekly" /DISABLE
endlocal

pause
