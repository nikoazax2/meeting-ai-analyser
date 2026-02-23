Set WshShell = CreateObject("WScript.Shell")
WshShell.Environment("Process")("PYTHONIOENCODING") = "utf-8"
WshShell.Environment("Process")("PATH") = WshShell.Environment("Process")("PATH") & ";C:\Users\nicolas.sage_neoteem\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\LocalCache\local-packages\Python313\site-packages\nvidia\cublas\bin"

' main.py gere tout : serveur + transcription + analyse en threads coordonnes
WshShell.Run "python ""C:\Projets\meeting-ai-analyser\main.py""", 0, False
