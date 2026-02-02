# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_submodules

spec_file = globals().get('__specfile__', 'iImport.spec')
project_dir = os.path.abspath(os.path.dirname(spec_file))
src_dir = os.path.join(project_dir, 'src')

datas = [
    (os.path.join(src_dir, 'ui', 'i18n'), os.path.join('ui', 'i18n')),
    (os.path.join(src_dir, 'ui', 'resources'), os.path.join('ui', 'resources')),
]

tools_dir = os.path.join(project_dir, 'tools')
if os.path.isdir(tools_dir):
    datas.append((tools_dir, 'tools'))

hiddenimports = collect_submodules('comtypes')

block_cipher = None

a = Analysis(
    ['src/main.py'],
    pathex=[project_dir],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='iImport',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='iImport',
)
