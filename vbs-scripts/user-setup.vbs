Option Explicit

' Per-user setup for Epiphany machines
' To be run as each individual user

' -------------------------------------------------------------------
' Version of this script.  Will only be re-run if the version changes.

Dim version
' Version must be an integer!
version = 7

' -------------------------------------------------------------------
' Global variables

Dim oWShell, oFS, oWNet, oShellApp

set oWShell = wscript.CreateObject("WScript.Shell")
Set oWNet = wscript.CreateObject("WScript.Network")
Set oFS = wscript.CreateObject("Scripting.FileSystemObject")
Set oShellApp = wscript.CreateObject("Shell.Application")

' Registry keys
Dim keyBase, lastVersionKey, lastRunTimestampKey, gvvsKey
keyBase = "HKCU\Software\Epiphany\UserSetup\"
lastVersionKey = keyBase & "lastVersion"
lastRunTimestampKey = keyBase & "lastRunTimestamp"
gvvsKey = keyBase & "GoogleVoiceAndVideoSetup"

' -------------------------------------------------------------------
' Find out who we are

'wscript.echo "Running on computer: " + oNet.ComputerName + ", " + oNet.Username + "@" + oNet.UserDomain

' -------------------------------------------------------------------
' When was the last time we ran?

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

Dim lastVersion
lastVersion = ReadKey(lastVersionKey)
' If the last version is this version, then there's nothing new to do
If (lastVersion <> "") Then
    If (Int(lastVersion) = version) Then
        wscript.Quit(0)
    End If
End If

' -------------------------------------------------------------------
' Remove pinned IE and Windows Media Player from taskbar.  Inspired
' from:
' http://social.technet.microsoft.com/Forums/en/w7itproinstall/thread/2f71c3df-6b42-4af9-88cc-2d12c8a1afdd

' Attempt unpinning one app in a specific directory
Sub unpin_app(basedir, App)
    If (oFS.FileExists(basedir & "\" & app)) Then
        Dim oVerb
        'wscript.echo "unpinning app: " & basedir & "\" & app
        For Each oVerb in oShellApp.Namespace(basedir).ParseName(App).Verbs
            If Replace(oVerb.name, "&", "") = "Unpin from Taskbar" Then
                'wscript.echo "Unpinning " & basedir & "\" & app
                oVerb.DoIt
                Exit Sub
            End if
        Next
        Set oVerb = nothing
    End If
End Sub

' For a given directory, unpin several apps
Sub unpin(basedir)
    If (oFS.FolderExists(basedir)) then
        Call unpin_app(basedir, "Internet Explorer.lnk")
        Call unpin_app(basedir, "Windows Media Player.lnk")
        Call unpin_app(basedir, "Mozilla Firefox\Mozilla Firefox.lnk")
        Call unpin_app(basedir, "Microsoft Office\Microsoft Office Word 2003.lnk")
        Call unpin_app(basedir, "Microsoft Office\Microsoft Office Excel 2003.lnk")
        Call unpin_app(basedir, "Microsoft Office\Microsoft Office Powerpoint 2003.lnk")
        Call unpin_app(basedir, "Microsoft Office\Microsoft Office Publisher 2003.lnk")

        Call unpin_app(basedir, "Microsoft Office\Microsoft Word 2010.lnk")
        Call unpin_app(basedir, "Microsoft Office\Microsoft Excel 2010.lnk")
        Call unpin_app(basedir, "Microsoft Office\Microsoft Powerpoint 2010.lnk")
        Call unpin_app(basedir, "Microsoft Office\Microsoft Publisher 2010.lnk")

        Call unpin_app(basedir, "Parish Data System\Church Office.lnk")
        Call unpin_app(basedir, "iTunes\iTunes.lnk")
    End If
End Sub

' Be thorough -- check all possible directories
Call unpin(oWShell.SpecialFolders.Item("StartMenu"))
Call unpin(oWShell.SpecialFolders.Item("Programs"))
Call unpin(oWShell.SpecialFolders.Item("AllUsersStartMenu"))
Call unpin(oWShell.SpecialFolders.Item("AllUsersPrograms"))

' -------------------------------------------------------------------
' Pin several things to the taskbar:
' Firefox
' PDS Church Office
' Word
' Excel
' Powerpoint
' iTunes

' Attempt pinning one app in a specific directory
Sub pin_app(basedir, App)
    If (oFS.FileExists(basedir & "\" & app)) Then
        Dim oVerb
        For Each oVerb in oShellApp.Namespace(basedir).ParseName(App).Verbs
            If Replace(oVerb.name, "&", "") = "Pin to Taskbar" Then
                oVerb.DoIt
                Exit Sub
            End if
        Next
        Set oVerb = nothing
    End If
End Sub

' For a given directory, pin several apps
Sub pin(basedir)
    If (oFS.FolderExists(basedir)) then
        Call pin_app(basedir, "Mozilla Firefox\Mozilla Firefox.lnk")
        Call pin_app(basedir, "Microsoft Office\Microsoft Office Word 2003.lnk")
        Call pin_app(basedir, "Microsoft Office\Microsoft Office Excel 2003.lnk")
        Call pin_app(basedir, "Microsoft Office\Microsoft Office Powerpoint 2003.lnk")
        Call pin_app(basedir, "Microsoft Office\Microsoft Office Publisher 2003.lnk")

        Call pin_app(basedir, "Microsoft Office\Microsoft Word 2010.lnk")
        Call pin_app(basedir, "Microsoft Office\Microsoft Excel 2010.lnk")
        Call pin_app(basedir, "Microsoft Office\Microsoft Powerpoint 2010.lnk")
        Call pin_app(basedir, "Microsoft Office\Microsoft Publisher 2010.lnk")

        Call pin_app(basedir, "Parish Data System\Church Office.lnk")
        Call pin_app(basedir, "iTunes\iTunes.lnk")
    End If
End Sub

' Be thorough -- check all possible directories
Call pin(oWShell.SpecialFolders.Item("StartMenu"))
Call pin(oWShell.SpecialFolders.Item("Programs"))
Call pin(oWShell.SpecialFolders.Item("AllUsersStartMenu"))
Call pin(oWShell.SpecialFolders.Item("AllUsersPrograms"))

' -------------------------------------------------------------------
' Set firefox to be the default browser
' Gah!  This somehow requires admin privs.  :-(

'Call oWShell.Run("firefox.exe -setDefaultBrowser -silent", 7, 1)

' -------------------------------------------------------------------

' Run the Google Voice and Video setup if it hasn't been run already
Dim gvvs, file
gvvs = ReadKey(gvvsKey)
' If we ran GVVS already, don't need to run it again
File = "C:\Epiphany\source\GoogleVoiceAndVideoSetup.exe"
If (gvvs = "" And oFS.FileExists(file)) Then
    Call owShell.Run(file)
    Call oWShell.RegWrite(gvvsKey, Now(), "REG_SZ")
End If

' -------------------------------------------------------------------
' Set the registry keys indicating that we ran
Call oWShell.RegWrite(lastVersionKey, Version, "REG_SZ")
Call oWShell.RegWrite(lastRunTimestampKey, Now(), "REG_SZ")

' -------------------------------------------------------------------
' Give indication that we're done

MsgBox "Epiphany user setup complete", vbOkOnly, "Epiphany user setup"
