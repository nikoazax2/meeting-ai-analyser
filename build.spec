# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec pour Meeting AI Analyser"""
import os
import site

block_cipher = None

# Trouver les binaires CTranslate2 et NVIDIA
site_packages = site.getsitepackages()[0]
ct2_path = os.path.join(site_packages, "ctranslate2")
nvidia_cublas = os.path.join(site_packages, "nvidia", "cublas", "bin")
nvidia_cudnn = os.path.join(site_packages, "nvidia", "cudnn", "bin")

binaries = []
# CTranslate2 libs
if os.path.isdir(ct2_path):
    for f in os.listdir(ct2_path):
        if f.endswith((".dll", ".so", ".pyd")):
            binaries.append((os.path.join(ct2_path, f), "ctranslate2"))

# NVIDIA CUDA (optionnel)
for nvidia_dir in [nvidia_cublas, nvidia_cudnn]:
    if os.path.isdir(nvidia_dir):
        for f in os.listdir(nvidia_dir):
            if f.endswith(".dll"):
                binaries.append((os.path.join(nvidia_dir, f), "."))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=[
        ('index.html', '.'),
        ('assets/app.ico', 'assets'),
    ],
    hiddenimports=[
        'faster_whisper',
        'ctranslate2',
        'pyaudiowpatch',
        'numpy',
        'scipy',
        'scipy.signal',
        'flask',
        'psutil',
        'live_transcribe',
        'analyst',
        'server',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'pytest'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='MeetingAIAnalyser',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/app.ico',
)
