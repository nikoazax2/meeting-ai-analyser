Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Resoudre le chemin du dossier du script (fonctionne peu importe ou le projet est)
strScriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

WshShell.Environment("Process")("PYTHONIOENCODING") = "utf-8"

' Ajouter le chemin NVIDIA CUDA si present (detection dynamique)
strNvidiaPath = WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Packages"
If fso.FolderExists(strNvidiaPath) Then
    ' Chercher le dossier Python dans les packages Windows Store
    Set objFolder = fso.GetFolder(strNvidiaPath)
    For Each subfolder In objFolder.SubFolders
        If Left(subfolder.Name, 30) = "PythonSoftwareFoundation.Pytho" Then
            strCublasPath = subfolder.Path & "\LocalCache\local-packages"
            ' Parcourir pour trouver le dossier site-packages\nvidia\cublas\bin
            If fso.FolderExists(strCublasPath) Then
                Set spFolder = fso.GetFolder(strCublasPath)
                For Each pyVer In spFolder.SubFolders
                    strCublasBin = pyVer.Path & "\site-packages\nvidia\cublas\bin"
                    If fso.FolderExists(strCublasBin) Then
                        WshShell.Environment("Process")("PATH") = WshShell.Environment("Process")("PATH") & ";" & strCublasBin
                    End If
                Next
            End If
        End If
    Next
End If

' main.py gere tout : serveur + transcription + analyse en threads coordonnes
WshShell.CurrentDirectory = strScriptDir
WshShell.Run "python """ & strScriptDir & "\main.py""", 0, False
