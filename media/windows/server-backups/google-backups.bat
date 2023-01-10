rem The folder C:\Epiphany_backups is backed up to Google Drive via
rem Google Backup and Sync.
rem
rem Once a day, via Windows Scheduled Tasks, run this script to
rem robocopy/xcopy sync a bunch of local folders to c:\Epiphany_backups
rem so that they get synced / backed up to Google Drive.

set target=C:\Epiphany_backups

rem Thumb drive letters can change.  Ensure that we robocopy the
rem actual DSX thumb drive, not some other disk.  Look for a sentinel
rem file that we know should only be on this thumb drive, and not
rem anywhere else.
set dsx=F:\
if exist %dsx%\DsxKey\DsxKeyData.xml (
   robocopy %dsx% "%target%\dsx-thumb-drive" /mir /e /r:0 /w:0
)

robocopy "C:\DSX 37151" "%target%\DSX 37151" /mir /e /r:0 /w:0
robocopy "C:\WinDSX" "%target%\WinSX" /mir /e /r:0 /w:0

robocopy "C:\PDSChurch\Data" "%target%\PDSChurch\Data" /mir /e /r:0 /w:0
robocopy "C:\PDSChurch\Backup" "%target%\PDSChurch\Backup" /mir /e /r:0 /w:0

xcopy "C:\Users\coeadmin\Ubuntu1804\rootfs\home\coeadmin\git\epiphany\media\windows\ECC-Ecobee\ECCEcobee.db" "%target%\ECCEcobee" /y
