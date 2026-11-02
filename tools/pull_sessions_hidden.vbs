' Runs tools/pull_sessions.sh with no window (the scheduled task "BobbyBones session pull" starts this with wscript.exe:
' bash.exe started directly by the task opens a console on the owner's screen). Waits for the pull and passes on its exit code.
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
script = Replace(fso.BuildPath(fso.GetParentFolderName(WScript.ScriptFullName), "pull_sessions.sh"), "\", "/")
bash = shell.ExpandEnvironmentStrings("%ProgramFiles%") & "\Git\bin\bash.exe"
WScript.Quit shell.Run("""" & bash & """ -lc """ & script & """", 0, True)
