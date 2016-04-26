Option Explicit

Const ENABLE_DEBUG = False

' Per-user setup for Epiphany machines
' To be run as each individual user

' -------------------------------------------------------------------
' Version of this script.  Will only be re-run if the version changes.

Dim version
' Version must be an integer!
version = 8

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
'If (lastVersion <> "") Then
'    If (Int(lastVersion) = version) Then
'        wscript.Quit(0)
'    End If
'End If

Const CSIDL_COMMON_PROGRAMS = &H17
Const CSIDL_PROGRAMS = &H2
Const CSIDL_STARTMENU = &Hb
Const CSIDL_ALL_USERS_DESKTOP = &H19
 
Dim objShell, objFSO, wshShell
Dim objCurrentUserStartFolder
Dim strCurrentUserStartFolderPath
Dim objAllUsersProgramsFolder
Dim strAllUsersProgramsPath
Dim objFolder
Dim objFolderItem
Dim colVerbs
Dim objVerb
Dim objAllUsersDesktop
Dim strAllUsersDesktop
Dim strUserIconFolder
Dim strAccessoriesIconFolder
Dim strAppData


Set objShell = CreateObject("Shell.Application")
Set objFSO = CreateObject("Scripting.FileSystemObject")

Set objCurrentUserStartFolder = objShell.NameSpace (CSIDL_STARTMENU)
strCurrentUserStartFolderPath = objCurrentUserStartFolder.Self.Path
Set objAllUsersProgramsFolder = objShell.NameSpace(CSIDL_COMMON_PROGRAMS)
strAllUsersProgramsPath = objAllUsersProgramsFolder.Self.Path
Set objAllUsersDesktop = objShell.NameSpace(CSIDL_ALL_USERS_DESKTOP)
strAllUsersDesktop = objAllUsersDesktop.Self.Path

Set wshShell = CreateObject( "WScript.Shell" )
strAppData = wshShell.ExpandEnvironmentStrings( "%APPDATA%" )



strUserIconFolder = strAppData & "\Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar"
strAccessoriesIconFolder = strCurrentUserStartFolderPath & "\Programs\Accessories"

'######################################################################
'######################################################################


' - Remove pinned items -
'Internet Explorer
unpinFromTaskbar strUserIconFolder, "Internet Explorer.lnk"
'My Computer
unpinFromTaskbar strUserIconFolder, "My Computer.lnk"
'Windows Explorer
unpinFromTaskbar strAccessoriesIconFolder, "Windows Explorer.lnk"
'Windows Media Player
unpinFromTaskbar strAllUsersProgramsPath, "Windows Media Player.lnk"


' - Pin to Taskbar -
'Windows Explorer
pinToTaskbar strAllUsersDesktop, "My Computer.lnk"
'Internet Explorer
pinToTaskbar strCurrentUserStartFolderPath & "\Programs", "Internet Explorer.lnk"
'Microsoft Word 2010
pinToTaskbar strAllUsersProgramsPath & "\Microsoft Office", "Microsoft Word 2010.lnk"
'Microsoft Excel 2010
pinToTaskbar strAllUsersProgramsPath & "\Microsoft Office" , "Microsoft Excel 2010.lnk"


' - Pin to Start Menu -
'Microsoft Word 2010
pinToStart strAllUsersProgramsPath & "\Microsoft Office", "Microsoft Word 2010.lnk"
'Microsoft Excel 2010
pinToStart strAllUsersProgramsPath & "\Microsoft Office", "Microsoft Excel 2010.lnk"



'######################################################################
'######################################################################

Function unpinFromTaskbar (strIconFolder, strIconFile)

	 If objFSO.FileExists(strIconFolder & "\" & strIconFile) Then
	    Set objFolder = objShell.Namespace(strIconFolder)
	    	Set objFolderItem = objFolder.ParseName(strIconFile)
		    Set colVerbs = objFolderItem.Verbs

		    	For Each objVerb in colVerbs
			    	 If Replace(objVerb.name, "&", "") = "Unpin from Taskbar" Then objVerb.DoIt
				    Next
				    End If
				    
End Function



Function pinToTaskbar (strIconFolder, strIconFile)
	 
	 If objFSO.FileExists(strIconFolder & "\" & strIconFile) Then
	    Set objFolder = objShell.Namespace(strIconFolder)
	    	Set objFolderItem = objFolder.ParseName(strIconFile)
		    Set colVerbs = objFolderItem.Verbs

		    	For Each objVerb in colVerbs
			    	 If Replace(objVerb.name, "&", "") = "Pin to Taskbar" Then objVerb.DoIt
				    Next
				    Else
					'wscript.echo strIconFolder & "\" & strIconFile
					End If

End Function

Function pinToStart(strIconFolder, strIconFile)
	 
	 If objFSO.FileExists(strIconFolder & "\" & strIconFile) Then
	    Set objFolder = objShell.Namespace(strIconFolder)
	    	Set objFolderItem = objFolder.ParseName(strIconFile)
		    Set colVerbs = objFolderItem.Verbs
		    
			For Each objVerb in colVerbs
			    	 If Replace(objVerb.name, "&", "") = "Pin to Start Menu" Then objVerb.DoIt
				    Next
				    Else
					'wscript.echo strIconFolder & "\" & strIconFile
					End If

End Function

Function unpinFromStart(strIconFolder, strIconFile)

	 If objFSO.FileExists(strIconFolder & "\" & strIconFile) Then
	    Set objFolder = objShell.Namespace(strIconFolder)
	    	Set objFolderItem = objFolder.ParseName(strIconFile)
		    Set colVerbs = objFolderItem.Verbs
		    
			For Each objVerb in colVerbs
			    	 If Replace(objVerb.name, "&", "") = "Unpin from Start Menu" Then objVerb.DoIt
				    Next
				    End If

End Function












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
	Call unpin_app(basedir, "Store.lnk")
	Call unpin_app(basedir, "Microsoft Edge.lnk")

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
' Set the registry keys indicating that we ran
Call oWShell.RegWrite(lastVersionKey, Version, "REG_SZ")
Call oWShell.RegWrite(lastRunTimestampKey, Now(), "REG_SZ")

' -------------------------------------------------------------------
' Give indication that we're done

MsgBox "Epiphany user setup complete", vbOkOnly, "Epiphany user setup"
