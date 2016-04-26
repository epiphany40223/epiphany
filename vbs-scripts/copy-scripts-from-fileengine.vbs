Option Explicit

' Run Rich tools copy or robocopy, with a little intelligence

' -------------------------------------------------------------------
' Global variables

' Various objects
Dim oWShell, oWNet, oFS
set oWShell = wscript.CreateObject("WScript.Shell")
Set oWNet = wscript.CreateObject("WScript.Network")
Set oFS = wscript.CreateObject("Scripting.FileSystemObject")

Dim scriptBase, scriptServer
scriptServer = "\\fileengine\scripts"
scriptBase = "C:\Epiphany\scripts"

' -------------------------------------------------------------------
' Should we use the MS rich tools or robocopy?

Dim str, copyCmd, q
q = Chr(34)
Str = "robocopy " & scriptServer & " " & scriptBase & " /mir /XD SNAPSHOTS"
copyCmd = Str

' -------------------------------------------------------------------
' Are we connected to the fileengine?  Look for the COE domain and H:.
' If not, silently exit.

If (oWNet.UserDomain <> "COE" Or Not oFS.DriveExists("H")) Then
    wscript.Quit(0)
End If

' -------------------------------------------------------------------
' Everything looks good; try to run the robocopy.
Call oWShell.Run(copyCmd, 0, 1)

' -------------------------------------------------------------------
' If C:\Epiphany\scripts\runme.vbs exists, run it
Dim file
file = scriptBase & "\runme.vbs"
If (oFS.FileExists(file)) Then
    Call oWShell.Run(file, 0, 1)
End If 
