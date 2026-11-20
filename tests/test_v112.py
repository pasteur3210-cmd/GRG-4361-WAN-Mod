from zipfile import ZipFile
from openpyxl import load_workbook
from unified_store import ensure_workbook, workbook_path
import unified_store

def test_upgrade_closes_zip_before_atomic_replace(tmp_path,monkeypatch):
    path=ensure_workbook(tmp_path)
    wb=load_workbook(path)
    try:
        del wb['Default Verification Summary']
        del wb['Default Verification Detail']
        wb.worksheets[0]['A2']='historic-row'
        wb.save(path)
    finally:
        wb.close()
    original_replace=unified_store.os.replace
    def checked_replace(src,dst):
        # Simulate Windows lock semantics for an archive opened by ensure_workbook.
        # The repaired ensure_workbook must finish its ZipFile context first.
        assert not any(f.filename==str(dst) for f in _active_archives)
        return original_replace(src,dst)
    _active_archives=[]
    original_zip=unified_store.zipfile.ZipFile
    class TrackingZip(original_zip):
        def __init__(self,file,*args,**kwargs):
            super().__init__(file,*args,**kwargs)
            self.filename=str(file)
            _active_archives.append(self)
        def close(self):
            super().close()
            if self in _active_archives:_active_archives.remove(self)
    monkeypatch.setattr(unified_store.zipfile,'ZipFile',TrackingZip)
    monkeypatch.setattr(unified_store.os,'replace',checked_replace)
    ensure_workbook(tmp_path)
    assert not _active_archives
    wb=load_workbook(path)
    try:
        assert len(wb.sheetnames)==5
        assert wb.worksheets[0]['A2'].value=='historic-row'
    finally:wb.close()
