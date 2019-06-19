rem The folder C:\Epiphany_backups is backed up to Google Drive via
rem Google Backup and Sync.
rem
rem Once a day, via Windows Scheduled Tasks, run this script to
rem robocopy sync a bunch of local folders to c:\Epiphany_backups
rem so that they get synced / backed up to Google Drive.

robocopy E:\ "C:\Epiphany_backups\dsx-e-thumb-drive" /mir /e /r:0 /w:0

robocopy "C:\DSX 37151" "C:\Epiphany_Backups\DSX 37151" /mir /e /r:0 /w:0
robocopy "C:\WinDSX" "C:\Epiphany_Backups\WinSX" /mir /e /r:0 /w:0

robocopy "C:\PDSChurch\Data" "C:\Epiphany_Backups\PDSChurch\Data" /mir /e /r:0 /w:0
robocopy "C:\PDSChurch\Backup" "C:\Epiphany_Backups\PDSChurch\Backup" /mir /e /r:0 /w:0
