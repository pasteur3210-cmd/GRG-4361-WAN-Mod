from PyInstaller.utils.hooks import collect_submodules
a = Analysis(['main.py'],pathex=[],binaries=[],datas=[('template.xlsx','.')],hiddenimports=collect_submodules('router_oqc'),hookspath=[],hooksconfig={},runtime_hooks=[],excludes=[],noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz,a.scripts,a.binaries,a.datas,[],name='GRG4361_WAN_Setting_V1.1.0',debug=False,bootloader_ignore_signals=False,strip=False,upx=False,console=False)
