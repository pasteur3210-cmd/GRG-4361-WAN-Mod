from pathlib import Path
import tempfile
import pytest
from wan_tool import (stable_records_dir, ledger_initialized, initialize_empty_ledger,
    reserve_ip, import_legacy_ledger, read_ledger, ledger_event)

def test_explicit_init_required():
    with tempfile.TemporaryDirectory() as td:
        assert not ledger_initialized(td)
        with pytest.raises(ValueError, match='not initialized'):
            reserve_ip(td,'001122AABBCC','CMTD22AABBCC','192.168.2.121','192.168.1.1','QA')
        assert initialize_empty_ledger(td)
        assert ledger_initialized(td)

def test_import_old_ip_prevents_reassignment():
    with tempfile.TemporaryDirectory() as td:
        legacy=Path(td)/'old';new=Path(td)/'new'
        initialize_empty_ledger(legacy)
        reserve_ip(legacy,'001122AABBCC','CMTD22AABBCC','192.168.2.121','192.168.1.1','QA')
        assert import_legacy_ledger(new,legacy/'WAN_IP_Allocation.csv')==1
        assert import_legacy_ledger(new,legacy/'WAN_IP_Allocation.csv')==0
        with pytest.raises(ValueError,match='already assigned'):
            reserve_ip(new,'001122AABBDD','CMTD22AABBDD','192.168.2.121','192.168.1.1','QA')
        assert len(read_ledger(new))==1

def test_conflicting_legacy_ledgers_block():
    with tempfile.TemporaryDirectory() as td:
        a,b,c=[Path(td)/n for n in ('a','b','c')]
        for folder,mac,gpon in [(a,'001122AABBCC','CMTD22AABBCC'),(b,'001122AABBDD','CMTD22AABBDD')]:
            initialize_empty_ledger(folder)
            reserve_ip(folder,mac,gpon,'192.168.2.121','192.168.1.1','QA')
        import_legacy_ledger(c,a/'WAN_IP_Allocation.csv')
        with pytest.raises(ValueError,match='Conflicting historical IP'):
            import_legacy_ledger(c,b/'WAN_IP_Allocation.csv')
        assert len(read_ledger(c))==1

def test_fixed_storage_path(monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA',r'C:\Users\QA\AppData\Local')
    assert stable_records_dir().parts[-2:] == ('GRG4361_WAN_Setting', 'records')
