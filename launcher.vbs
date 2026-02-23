Set WshShell = CreateObject("WScript.Shell")
WshShell.Environment("Process")("PYTHONIOENCODING") = "utf-8"
WshShell.Environment("Process")("PATH") = WshShell.Environment("Process")("PATH") & ";C:\Users\nicolas.sage_neoteem\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\LocalCache\local-packages\Python313\site-packages\nvidia\cublas\bin"

' Transcription audio (invisible)
WshShell.Run "python ""C:\Projets\meeting-ai-analyser\live_transcribe.py"" --mic-device 11", 0, False

WScript.Sleep 8000

' Claude analyse (invisible)
WshShell.Run "python ""C:\Projets\meeting-ai-analyser\analyst.py""", 0, False

' Serveur web (invisible)
WshShell.Run "python ""C:\Projets\meeting-ai-analyser\server.py""", 0, False

WScript.Sleep 3000

' Ouvrir le navigateur
WshShell.Run "http://localhost:5555", 1, False
