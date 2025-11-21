# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['daily_reminder_qt61017.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('app_icon.ico', '.'),      # 主程序图标
        ('tray_icon.ico', '.'),     # 托盘图标
    ],
    hiddenimports=[
        'PyQt6.QtCore',
        'PyQt6.QtGui', 
        'PyQt6.QtWidgets',
        'chinese_calendar',
        'lunardate',
        'requests',
        'openpyxl',
        'dateutil',
        'winreg',
    ],
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
    name='每日工作提醒',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app_icon.ico',  # 设置exe文件图标
)
