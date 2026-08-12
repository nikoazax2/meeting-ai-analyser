# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Meeting AI Analyser"""
import os
import site

block_cipher = None

# Find CTranslate2 and NVIDIA binaries
site_packages = site.getsitepackages()[0]
ct2_path = os.path.join(site_packages, "ctranslate2")
nvidia_cublas = os.path.join(site_packages, "nvidia", "cublas", "bin")
nvidia_cudnn = os.path.join(site_packages, "nvidia", "cudnn", "bin")

# Find faster_whisper assets via the actual module path
import faster_whisper as _fw
faster_whisper_assets = os.path.join(os.path.dirname(_fw.__file__), "assets")

binaries = []
# CTranslate2 libraries
if os.path.isdir(ct2_path):
    for f in os.listdir(ct2_path):
        if f.endswith((".dll", ".so", ".pyd")):
            binaries.append((os.path.join(ct2_path, f), "ctranslate2"))

# NVIDIA CUDA (optional)
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
        ('images', 'images'),
        (faster_whisper_assets, 'faster_whisper/assets'),
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
        'paths',
        'version',
        'settings',
        'license',
        'hwid',
        'telemetry',
        'updater',
        'live_transcribe',
        'analyst',
        'server',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # None of these are imported anywhere in this app. They get pulled in
    # transitively from the dev environment and cost ~400 MB uncompressed:
    # torch alone is 181 MB, and faster-whisper runs on ctranslate2, not torch.
    # Keep av, onnxruntime, tokenizers and ctranslate2 - faster-whisper needs
    # them for decoding, VAD and tokenisation.
    excludes=[
        'tkinter', 'matplotlib', 'pytest',
        'torch', 'torchvision', 'torchaudio',
        'transformers', 'datasets', 'accelerate',
        'spacy', 'thinc', 'blis', 'cymem', 'preshed', 'murmurhash',
        'srsly', 'catalogue', 'wasabi', 'weasel', 'confection',
        'imageio', 'imageio_ffmpeg',
        'botocore', 'boto3', 's3transfer',
        'pandas', 'sympy', 'networkx',
        'IPython', 'notebook', 'jupyter',
        'pygame',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Drop Intel MKL. PyInstaller pulls ~400 MB of it in from Library/bin, but numpy
# and scipy here are built against OpenBLAS - `numpy.show_config()` reports
# openblas64 - so none of it is ever loaded. Leaving it in tripled the installer
# (170 MB -> 493 MB), which is a real cost on a product whose main problem is
# getting people past the download in the first place.
_EXCLUDED_BINARY_PREFIXES = ('mkl_',)

_kept, _dropped_bytes = [], 0
for _entry in a.binaries:
    _name = os.path.basename(_entry[0]).lower()
    if _name.startswith(_EXCLUDED_BINARY_PREFIXES):
        try:
            _dropped_bytes += os.path.getsize(_entry[1])
        except OSError:
            pass
        continue
    _kept.append(_entry)

print(f"[spec] excluded {len(a.binaries) - len(_kept)} binaries "
      f"({_dropped_bytes / 1048576:.0f} MB) matching {_EXCLUDED_BINARY_PREFIXES}")
a.binaries = _kept

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
