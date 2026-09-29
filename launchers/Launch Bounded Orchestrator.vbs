Option Explicit

Dim shell, picker, folder, fs, scriptPath, command, candidate
Set shell = CreateObject("WScript.Shell")
Set picker = CreateObject("Shell.Application")
Set folder = picker.BrowseForFolder(0, "Choose the project folder to configure", 1, 0)
If folder Is Nothing Then WScript.Quit 0

Set fs = CreateObject("Scripting.FileSystemObject")
scriptPath = fs.BuildPath(fs.GetParentFolderName(WScript.ScriptFullName), "launch_dashboard.py")
If Not fs.FileExists(scriptPath) Then
    MsgBox "The launcher must stay inside its distribution folder.", vbExclamation, "Setup console unavailable"
    WScript.Quit 1
End If

On Error Resume Next
For Each candidate In Array("pyw.exe -3", "pythonw.exe")
    command = candidate & " " & Chr(34) & scriptPath & Chr(34) & " " & Chr(34) & folder.Self.Path & Chr(34)
    Err.Clear
    shell.Run command, 0, False
    If Err.Number = 0 Then WScript.Quit 0
Next
On Error GoTo 0

MsgBox "Install Python 3.11 or newer, then open this launcher again.", vbExclamation, "Python is needed"
WScript.Quit 1
