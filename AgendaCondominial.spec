# Build on Windows: python -m PyInstaller --clean --noconfirm AgendaCondominial.spec
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files
root = Path(SPECPATH)
a = Analysis([str(root / 'main.py')], pathex=[str(root)],
    binaries=[], datas=[(str(root / 'app' / 'assets'), 'app/assets')] + collect_data_files('tzdata'),
    hiddenimports=['sqlalchemy.dialects.sqlite', 'tzdata'],
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='AgendaCondominial',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, disable_windowed_traceback=False, icon=str(root / 'app' / 'assets' / 'app.ico'))
