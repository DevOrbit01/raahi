# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[],
    datas=collect_data_files('customtkinter') + collect_data_files('cloakbrowser'),
    hiddenimports=collect_submodules('cloakbrowser') + [
        'customtkinter',
        'PIL',
        'PIL._tkinter_finder',
        'openpyxl',
        'requests',
        'bs4',
        'urllib3',
        'cloudscraper',
        'playwright',
        'playwright.sync_api',
        'requests_toolbelt',
        'app_paths',
        'packaging_check',
        'scrapers.baanknet',
        'scrapers.baanknet_ibc',
        'scrapers.baanknet_vehicle',
        'scrapers.baanknet_property',
        'scrapers.eauctionsindia',
        'scrapers.local_browser',
        'scrapers.scrape_progress',
        'sqlite3',
        'scrapers.bankauctions',
        'scrapers.bankauction',
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
    name='RaahiScraper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to False to hide console window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add 'icon.ico' if you have an icon file
)
