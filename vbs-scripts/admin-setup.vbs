Option Explicit

' Administrative setup for Epiphany machines
' Requires elevated privledges

' -------------------------------------------------------------------
' Re-launch With escalated privs If necessary.  Inspired from
' http://www.winhelponline.com/articles/185/1/VBScripts-and-UAC-elevation.html.

Dim oShellApp
Set oShellApp = CreateObject("Shell.Application")
If (0 = WScript.Arguments.length) Then
    ' Pass a bogus argument just to avoid this if block again
    oShellApp.ShellExecute "wscript.exe", Chr(34) & WScript.ScriptFullName & Chr(34) & " uac", "", "runas", 1
    wscript.Quit(0)
End If

' -------------------------------------------------------------------
' Global variables

Dim oWShell, oFS, oWNet

set oWShell = wscript.CreateObject("WScript.Shell")
Set oWNet = wscript.CreateObject("WScript.Network")
Set oFS = wscript.CreateObject("Scripting.FileSystemObject")

' -------------------------------------------------------------------
' Find out who we are

'wscript.echo "Running on computer: " + oWNet.ComputerName + ", " + oWNet.Username + "@" + oWNet.UserDomain

' -------------------------------------------------------------------
' Create C:\Epiphany\scripts and C:\Epiphany\media
' Set permissions appropriately
Dim Dir

Dir = "C:\Epiphany"
If (Not oFS.FolderExists(dir)) Then
    oFS.CreateFolder(dir)
End If
Dir = "C:\Epiphany\scripts"
If (Not oFS.FolderExists(dir)) Then
    oFS.CreateFolder(dir)
End If

' Set permissions by calling icacls so that all users can run them
Call owShell.Run("icacls C:\Epiphany\scripts /t /grant users:rx")

' -------------------------------------------------------------------
' Copy GVV setup down if it's not already here

' THIS DOESN'T WORK BECAUSE ADMINISTRATOR DOESN'T HAVE RIGHTS TO
' \\media\media -- AND THIS SCRIPT RUNS AS ADMINISTRATOR (not a
' user who has access to \\media\media)
Dim file
File = "C:\Epiphany\source\GoogleVoiceAndVideoSetup.exe"
If (Not oFS.FileExists(file)) Then
    Dim file2
    file2 = "\\media\media\Google\GoogleVoiceAndVideoSetup.exe"
    If (oFS.FileExists(file2)) Then
        Dim fileObj
        Set fileObj = oFs.GetFile(file2)
        fileObj.Copy(file)
    End If
End If

' -------------------------------------------------------------------
' Remove several links from all users desktop

Dim oFolder, oFolderItem

Dir = oWShell.SpecialFolders.Item("AllUsersDesktop")
Call removeRegexpFiles(Dir)
Dir = oWShell.SpecialFolders.Item("Desktop")
Call removeRegexpFiles(Dir)

Sub removeRegexpFiles(Dir)
    Set oFolder = oFS.GetFolder(Dir)
    If (Not oFolder Is nothing) Then
        Dim adobe
        Dim picasa
        Dim firefox
        Dim church_office
        Dim itunes
        Dim chrome
        Dim roxio
        Dim quicktime
        Dim dell
        
        Set dell = New RegExp
        dell.IgnoreCase = True
        dell.Pattern = "^Dell .+$"
        
        Set chrome = New RegExp
        chrome.IgnoreCase = True
        chrome.Pattern = "^Google Chrome$"
        
        Set roxio = New RegExp
        roxio.IgnoreCase = True
        roxio.Pattern = "^Roxio .+$"
        
        Set quicktime = New RegExp
        quicktime.IgnoreCase = True
        quicktime.Pattern = "^Quicktime .+$"
        
        Set adobe = New RegExp
        adobe.IgnoreCase = True
        adobe.Pattern = "^adobe .+$"
        
        Set picasa = New RegExp
        picasa.IgnoreCase = True
        picasa.Pattern = "^picasa \d+$"
        
        Set firefox = New RegExp
        firefox.IgnoreCase = True
        firefox.Pattern = "^mozilla firefox$"
        
        Set church_office = New RegExp
        church_office.IgnoreCase = True
        church_office.Pattern = "^church office$"
        
        Set itunes = New RegExp
        itunes.IgnoreCase = True
        itunes.Pattern = "^itunes$"
        
        Dim oFile
        For Each oFile in oFolder.Files
            Rem If this Is Not a link, skip it
            Dim Name
            Name = oFS.GetExtensionName(oFile.Name)
            If (Name = "lnk" Or name = "url") Then
                Rem Get the basename (e.g., without the filename extension)
                Name = oFS.GetBaseName(oFile.Name)
                If (adobe.test(Name) Or picasa.test(Name) Or firefox.test(Name) Or church_office.test(Name) Or itunes.test(Name) Or dell.test(Name) Or chrome.test(Name) Or roxio.test(Name) Or quicktime.test(Name)) Then
                    oFile.Delete
                    'Wscript.echo "Deleted common desktop link: " + Name
                End If
            End If
        Next
    End If
End Sub

' -------------------------------------------------------------------
' Ambiguous jumplist support in Firefox at the moment, so let's just
' put a shortcut on the desktop for Epiphany gmail.

Dim oShortcut

Dir = oWShell.SpecialFolders.Item("AllUsersDesktop")
Set oFolder = oFS.GetFolder(Dir)

If (Not oFolder Is nothing) Then
    ' Epiphany Gmail
    file = Dir + "\Epiphany Gmail.url"
    If (oFS.FileExists(File)) Then
        oFS.DeleteFile(file)
    End If
    set oShortcut = oWShell.CreateShortcut(file)
    oShortcut.TargetPath = "https://mail.google.com/"
    oShortcut.Save()

    ' Backup to fileengine
    file = Dir + "\Backup to Fileengine.lnk"
    If (oFS.FileExists(File)) Then
        oFS.DeleteFile(file)
    End If
    set oShortcut = oWShell.CreateShortcut(file)
    oShortcut.Description = "Backup all 'My Documents' files to the fileengine"
    oShortcut.TargetPath = "C:\Epiphany\scripts\backup to fileengine.vbs"
    oShortcut.WindowStyle = 7
    oShortcut.Save()
End If

' -------------------------------------------------------------------
' Desktop link to emacs, just for administrator

Dir = oWShell.SpecialFolders.Item("Desktop")
Set oFolder = oFS.GetFolder(Dir)
If (Not oFolder Is nothing) Then
    ' Emacs
    file = Dir + "\Emacs.lnk"
    If (oFS.FileExists(File)) Then
        oFS.DeleteFile(file)
    End If
    set oShortcut = oWShell.CreateShortcut(file)
    oShortcut.TargetPath = "C:\Epiphany\emacs-23.2\bin\runemacs.exe"
    oShortcut.Description = "Emacs"
    oShortcut.Save()
End If

' -------------------------------------------------------------------
' Reset the PDS link to point to the \\fileengine data

Dir = oWShell.SpecialFolders.Item("AllUsersPrograms")
Set oFolder = oFS.GetFolder(dir)
If (Not oFolder Is nothing) Then
    file = Dir + "\Parish Data System\Church Office.lnk"
    If (oFS.FileExists(File)) Then
        set oShortcut = oWShell.CreateShortcut(file)
        oShortcut.Arguments = "P=C:\PDSChurch D=\\fileengine\PDSChurch N=1"
        oShortcut.Save()
    End if
End If

Dir = oWShell.SpecialFolders.Item("AllUsersDesktop")
Set oFolder = oFS.GetFolder(dir)
If (Not oFolder Is nothing) Then
    file = Dir + "\Church Office.lnk"
    If (oFS.FileExists(File)) Then
        set oShortcut = oWShell.CreateShortcut(file)
        oShortcut.Arguments = "P=C:\PDSChurch D=\\fileengine\PDSChurch N=1"
        oShortcut.Save()
    End if
End If

' -------------------------------------------------------------------
' Give indication that we're done

MsgBox "Epiphany administrative setup complete", vbOkOnly, "Epiphany admin setup"
