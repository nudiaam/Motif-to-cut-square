Option Explicit

Dim shell, fileSystem, projectFolder, shortcutPath, launcherPath, iconPath, shortcut

Set shell = CreateObject("WScript.Shell")
Set fileSystem = CreateObject("Scripting.FileSystemObject")

If WScript.Arguments.Count > 0 Then
    projectFolder = fileSystem.GetAbsolutePathName(WScript.Arguments(0))
Else
    projectFolder = fileSystem.GetParentFolderName( _
        fileSystem.GetParentFolderName( _
            fileSystem.GetParentFolderName(WScript.ScriptFullName)))
End If

shortcutPath = fileSystem.BuildPath(projectFolder, "Lalikul Cut Prep.lnk")
launcherPath = fileSystem.BuildPath(projectFolder, "Lalikul Cut Prep.vbs")
iconPath = fileSystem.BuildPath(projectFolder, "app\assets\lalikul-cut-prep.ico")

Set shortcut = shell.CreateShortcut(shortcutPath)
shortcut.TargetPath = shell.ExpandEnvironmentStrings("%SystemRoot%\System32\wscript.exe")
shortcut.Arguments = Quote(launcherPath)
shortcut.WorkingDirectory = projectFolder
shortcut.IconLocation = iconPath & ",0"
shortcut.Description = "Open Lalikul Cut Prep without a terminal window"
shortcut.WindowStyle = 1
shortcut.Save

WScript.Echo "Shortcut created: " & shortcutPath

Function Quote(value)
    Quote = Chr(34) & value & Chr(34)
End Function
