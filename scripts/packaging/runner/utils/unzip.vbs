Set ArgObj = WScript.Arguments

If (Wscript.Arguments.Count > 0) Then
 inputFile = ArgObj(0)
Else
 WScript.Quit 1
End if

Dim cwd
cwd = CreateObject("Scripting.FileSystemObject").GetAbsolutePathName(".")

zipFile = cwd & "\" & inputFile
outFolder = cwd & "\"

Set objShell = CreateObject("Shell.Application")
Set objSource = objShell.NameSpace(zipFile).Items()
Set objTarget = objShell.NameSpace(outFolder)

objTarget.CopyHere objSource, 256
