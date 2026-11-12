' 1.9a: the night's measurements (and the start on the owner's word) with no window at all (CLAUDE.md, global: unattended jobs never open a window).
' wscript.exe night_prep.vbs [start|resume]
Dim sh, here, args
Set sh = CreateObject("WScript.Shell")
here = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
args = ""
If WScript.Arguments.Count > 0 Then
    If WScript.Arguments(0) = "start" Then args = " -Start"
    If WScript.Arguments(0) = "resume" Then args = " -Resume"
End If
sh.CurrentDirectory = here & "\..\..\..\.."
sh.Run "powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & here & "\night_prep.ps1""" & args, 0, True
