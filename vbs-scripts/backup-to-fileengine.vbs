Option Explicit

' Run Rich tools copy or robocopy, with a little intelligence

' -------------------------------------------------------------------
' Global variables

' Various objects
Dim oWShell, oWNet, oFS
set oWShell = wscript.CreateObject("WScript.Shell")
Set oWNet = wscript.CreateObject("WScript.Network")
Set oFS = wscript.CreateObject("Scripting.FileSystemObject")

' Registry keys
Dim keyBase, lastSuccessTimestampKey, lastWarnTimestampKey
keyBase = "HKCU\Software\Epiphany\BackupToFileengine\"
lastSuccessTimestampKey = keyBase & "lastSuccessTimestamp"
lastWarnTimestampKey = keyBase & "lastWarnTimestamp"

' When run interactively, print warnings.  When run automated (e.g.,
' via cron/scheduler), don't print warnings -- only print errors.
Dim suppressWarnings
suppressWarnings = 0

' -------------------------------------------------------------------
' If this was run non-interactively (i.e., with the /nowarn argument),
' then suppress warnings.
Dim i
i = 0
Do While (i < wscript.Arguments.Count)
    If (LCase(wscript.Arguments.item(i)) = "/nowarn") Then
        suppressWarnings = 1
    End If 
Loop

' -------------------------------------------------------------------
' Should we use the MS rich tools or robocopy?

Dim file, str, backupCmd
' Rich copy doesn't seem to delete files at the destination if they're
' deleted at the source.  There's probably an option to specify this,
' but I don't feel like figuring it out.  So we're going with robocopy
' for now (plus, robocopy is installed everywhere already).
file = "BOGUS C:\Program Files\Microsoft Rich Tools\RichCopy 4.0\richcopy.exe"
If (oFS.FileExists(file)) Then
    Dim q
    q = Chr(34)
    Str = q & "C:\Program Files\Microsoft Rich Tools\RichCopy 4.0\richcopy"
    Str = Str & q & " " & q & "%USERPROFILE%\Documents" & q & " " & q
    Str = Str & "\\fileengine\%USERNAME%\Documents" & q
    Str = Str & " /FSD /TSD /TSU /QA /QP /P " & q
    Str = Str & "C:\Epiphany\Rich copy logs\report.log" & q
    Str = Str & " /UE /US /UD /UC /UPF /UPC /UPS /UFC /UCS /USC /USS /USD /UPR /UET"
Else
    Str = "robocopy " & q & "%USERPROFILE%\Documents" & q & " " & q
    Str = Str & "\\fileengine\%USERNAME%\Documents" & q & " /mir /e /r:0 /w:0"
End If
backupCmd = Str

' -------------------------------------------------------------------
' When was the last time we ran successfully?

' Read a key from the registry.  If we error while reading the key,
' assume that parts of it do not exist and try to create all the parts
' leading up to that key (by writing blank values to them).
Function ReadKey(Name)
    On Error Resume Next

    Err.Clear
    ReadKey = oWShell.RegRead(Name)

    If (Err.Number <> 0) Then
        Err.Clear
        Dim parts, tmp, i

        ' Loop creating the parts if they don't exist.  We know that
        ' the first 2 parts will already exist, so start with those as
        ' a base.
        parts = split(Name, "\")
        tmp = parts(0) & "\" & parts(1)
        i = 2
        Do While (tmp <> Name)
            tmp = tmp & "\" & parts(i)
            i = i + 1

            Err.Clear
            oWShell.RegRead(tmp)
            If (Err.Number <> 0) Then
                Err.Clear
                Call oWShell.RegWrite(tmp, "", "REG_SZ")
                If (Err.Number <> 0) Then
                    MsgBox "Cannot write to registry key: " & Name & " (tried " & tmp & ")", vbOKOnly, "Epiphany Debug"
                    wscript.Quit(1)
                End If 
            End If
        Loop
          
        ' Now it should exist.  Read it.
        Err.Clear
        ReadKey = oWShell.RegRead(Name)
        If (Err.Number <> 0) Then 
            MsgBox "Cannot read registry key: " & Name, vbOKOnly, "Epiphany Debug"
            wscript.Quit(1)
        End If 
    End If
End Function

Dim tmp, startTimestamp, minsSinceLastSuccess, minsSinceLastWarn

' Number of minutes since we last ran a successful backup
startTimestamp = Now
tmp = ReadKey(lastSuccessTimeStampKey)
If (tmp <> "") Then 
    minsSinceLastSuccess = DateDiff("n", tmp, startTimestamp)
Else
    minsSinceLastSuccess = -1
End If

' Numer of minutes since our last warning message
tmp = ReadKey(lastSuccessTimeStampKey)
If (tmp <> "") Then 
    minsSinceLastWarn = DateDiff("n", tmp, startTimestamp)
Else
    minsSinceLastWarn = -1
End If 

' -------------------------------------------------------------------
' Subroutine to print a message about why the backup failed and quit.
' May optionally print an additional message if it has been far too
' long since we've had a successful backup.

Sub printBackupFailed(Str, isWarning)
    Dim forceDisplay
    forceDisplay = 0
    
    If (minsSinceLastSuccess >= (7 * 60 * 24)) Then
        Str = "NOTE: It has been over 7 days since have have successfully run a backup to the Epiphany FileEngine.  This is bad Bad BAD!" & vbCrLF & vbCrLF & Str

        ' Has it been over a day since we warned last?  If so, then
        ' upgrade this from a warning to an error (errors are always
        ' displayed).
        If (minsSinceLastWarn >= (7 * 60 * 24)) then
            isWarning = 0
        End If
    End If 

    ' Only print the message if: 1) this is an error, or 2) this is a
    ' warning and we're not suppressing warnings
    If (Not isWarning Or (isWarning And Not suppressWarnings)) Then
        ' Update the reg key with the last warning time.  Do it now
        ' before displaying the MsgBox because we don't want to wait
        ' for the user to click "ok" before updating the timestamp.
        Call oWShell.RegWrite(lastWarnTimestampKey, Now(), "REG_SZ")

        ' Display the warning message box
        MsgBox Str, (vbOKOnly + vbExclamation), "Backup to Epiphany FileEngine failed"
    End If

    ' Quit
    wscript.Quit(1)
End sub

' -------------------------------------------------------------------
' Are we connected to the fileengine?  Look for the COE domain and H:.

If (oWNet.UserDomain <> "COE" Or Not oFS.DriveExists("H")) Then
    Str = "You do not appear to be connected to the Epiphany network, and therefore cannot perform a backup to the FileEngine file server."
    Str = Str & vbCrLf & vbCrLf
    Str = Str & "Please try again when you are connected to the Epiphany network."

    ' Use a subroutine to print the message; it will check to see if
    ' it has been too long since we've run successfully.  If so, it'll
    ' print an additional error message.  The subroutine won't return.
    Call printBackupFailed(Str, 0)
End If

' -------------------------------------------------------------------
' Everything looks good; try to run the backup.  Do this in a
' subroutine just so that we can catch the error if it fails.

Sub doTheBackup
    On Error Resume Next

    Err.Clear
    Call oWShell.Run(backupCmd, 1, 1)
    If (Err.Number <> 0) Then
        Err.Clear
        
        Str = "Backup failed!  Error: " & Err.Number
        Str = Str & vbCrLf & vbCrLf
        Str = Str & Err.Description
        Str = Str & vbCrLf & vbCrLf
        Str = Str & "Please try again, or contact the Epiphany Tech Committee for help"

        ' See comment above about why we use a subroutine to print the
        ' error message.
        Call printBackupFailed(Str, 1)
    End If 
End Sub

Call doTheBackup

' -------------------------------------------------------------------
' If it all succeeds, we fall through to here.  Write the timestamp in
' the registry of the last successful run.

Call oWShell.RegWrite(lastSuccessTimestampKey, Now(), "REG_SZ")
