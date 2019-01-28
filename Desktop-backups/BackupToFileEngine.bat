@echo off
setlocal

rem - get/set vars to script locations
set SrcDir=%~dp0
set ServerDir="\\fileengine\%USERNAME%"
set LogFile=%SrcDir%\BackupLog.txt
set ServerLogFile="%ServerDir%\Backup\BackupLog.txt"
set BackupWorked=true

echo .
echo Backup to Epiphany FileEngine
echo Note:  YOU MUST BE ON THE EPIPHANY CAMPUS TO RUN THE BACKUP!
echo .

goto :BackupNow

if exist %ServerDir% goto :BackupNow
echo .
call :LogResults "Not on the Epiphany network!"
goto :Done


:BackupNow
call :DoTheBackup	"C:\WinDSX"				"WinDSX"
call :DoTheBackup	"C:\media"				"Media"
call :DoTheBackup	"%USERPROFILE%\Desktop"			"Desktop"
call :DoTheBackup	"%USERPROFILE%\Documents"		"Documents"
call :DoTheBackup	"%USERPROFILE%\Documents\Pictures"	"Pictures"


echo .
if "%BackupWorked%" == "true" call :LogResults "Backup Complete"
goto :Done


:DoTheBackup
	set BackupSrc="%~1"
	set BackupDst="%ServerDir%\Backup\%~2"
	rem skip the backup if the source directory does not exist
	if not exist %BackupSrc% goto :eof

	set BackupCmd=robocopy
	set BackupParms=/mir /e /r:0 /w:0

	echo Backing up %BackupSrc% to %BackupDst%
	%BackupCmd% %BackupSrc% %BackupDst% %BackupParms%
	IF /I %ERRORLEVEL% GEQ 8 call :LogResults "%BackupCmd% of %BackupSrc% failed!"
	echo .
goto :eof


:LogResults
	set BackupWorked=false
	echo .
	echo %~1
	echo At %time% on %date% : %~1 >> %LogFile%
	if exist %ServerDir% echo At %time% on %date% : %~1 >> %ServerLogFile%
goto :eof


:Done
endlocal

