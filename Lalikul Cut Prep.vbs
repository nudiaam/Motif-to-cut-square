Option Explicit

Dim shell, fileSystem, projectFolder, runtimeExe, pythonExe, pythonwExe, checkCommand, result

Set shell = CreateObject("WScript.Shell")
Set fileSystem = CreateObject("Scripting.FileSystemObject")

projectFolder = fileSystem.GetParentFolderName(WScript.ScriptFullName)
runtimeExe = fileSystem.BuildPath(projectFolder, ".runtime\python.exe")
pythonExe = fileSystem.BuildPath(projectFolder, ".venv\Scripts\python.exe")
pythonwExe = fileSystem.BuildPath(projectFolder, ".venv\Scripts\pythonw.exe")

If Not fileSystem.FileExists(runtimeExe) Or _
        Not fileSystem.FileExists(pythonExe) Or _
        Not fileSystem.FileExists(pythonwExe) Then
    MsgBox "The local application runtime is missing." & vbCrLf & vbCrLf & _
        "Double-click setup.bat first, then try again.", _
        vbExclamation, "Lalikul Cut Prep"
    WScript.Quit 1
End If

shell.CurrentDirectory = projectFolder
checkCommand = Quote(pythonExe) & _
    " -c " & Quote("import PySide6, cv2, numpy, app.main")
result = shell.Run(checkCommand, 0, True)

If result <> 0 Then
    MsgBox "The application environment is incomplete or broken." & vbCrLf & vbCrLf & _
        "Double-click setup.bat to repair it. If the problem continues, use run_console.bat " & _
        "to see the technical error.", _
        vbCritical, "Lalikul Cut Prep"
    WScript.Quit result
End If

shell.Run Quote(pythonwExe) & " -m app.main", 0, False

Function Quote(value)
    Quote = Chr(34) & value & Chr(34)
End Function
