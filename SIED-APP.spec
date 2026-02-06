# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

# NOTE: keep the UNC path unicode-safe (avoid mojibake on some code pages).
datas = [
    ('templates', 'templates'),
    ('static', 'static'),
    ('images', 'images'),
    ('\\\\Sbureautique\\sied\\ndpartage\\Dépendance\\instantclient_23_8', 'instantclient_23_8'),
    ('oracle_net', 'oracle_net'),
]
binaries = []
hiddenimports = []
tmp_ret = collect_all('oracledb')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('cryptography')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='SIED-APP',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='version.txt',
    icon=['images\\logo.ico'],
)
