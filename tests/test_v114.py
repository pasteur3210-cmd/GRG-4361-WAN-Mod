"""V1.1.4: new batch isolation, permanent records, restore verification continuity."""
import json
import zipfile
import pytest
from pathlib import Path
from batch_manager import active_batch, new_batch, validate_batch_id
from default_verify import install_reference_if_missing, load_baseline
from unified_store import ensure_workbook, add_history, reserve, read_rows, workbook_path, ip_state, add_default_verification

MAC1='3872C0112255'
MAC2='1C6499ABE129'


def test_legacy_preserved_new_batches_reset_and_reopen(tmp_path):
    root = tmp_path/'records'
    ensure_workbook(root)
    install_reference_if_missing(root)
    old_gold = load_baseline(root)['sha256']
    add_history(root, 'V1.1.3', 'Production', '192.168.1.1', 'APPLY', 'OK', MAC1,
                'CMTDC0112255', '192.168.2.121', 'QA', 'prior batch')
    reserve(root, 'Production','QA',MAC1,'CMTDC0112255','192.168.2.121','192.168.1.1')
    legacy_bytes=workbook_path(root).read_bytes()
    assert active_batch(root)==('LEGACY',root)
    new_dir=new_batch(root,'MP20261123_001','QA',True)
    assert new_dir==root/'batches'/'MP20261123_001'
    assert active_batch(root)==('MP20261123_001',new_dir)
    assert workbook_path(root).read_bytes()==legacy_bytes
    assert ip_state(new_dir)=={}
    assert load_baseline(new_dir)['sha256']==old_gold
    reserve(new_dir,'Production','QA',MAC2,'CMTD99ABE129','192.168.2.121','192.168.1.1')
    assert len(read_rows(new_dir,1))==1
    assert len(read_rows(root,1))==1
    new2=new_batch(root,'MP20261123_002','QA',True)
    assert ip_state(new2)=={}
    assert len(read_rows(new_dir,1))==1
    assert load_baseline(new2)['sha256']==old_gold
    assert active_batch(root)==('MP20261123_002',new2)
    with zipfile.ZipFile(workbook_path(new2)) as z:
        assert z.testzip() is None
        assert 'xl/worksheets/sheet5.xml' in z.namelist()


def test_duplicate_batch_and_unsafe_path_rejected(tmp_path):
    root=tmp_path/'records';root.mkdir()
    for name in ['../escape','a/b', '..', 'A B', '', 'x'*49, 'LEGACY']:
        with pytest.raises(ValueError):validate_batch_id(name)
    with pytest.raises(ValueError):new_batch(root,'RUN1','QA',False)
    assert not (root/'active_batch.json').exists()
    new_batch(root,'RUN1','QA',True)
    with pytest.raises((FileExistsError, ValueError)):new_batch(root,'RUN1','QA',True)
    with pytest.raises(ValueError):new_batch(root,'RUN2','',True)
    assert active_batch(root)[0]=='RUN1'


def test_default_verification_is_written_in_current_batch_only(tmp_path):
    root=tmp_path/'records'
    a=new_batch(root,'RUN001','QA',True)
    add_history(a,'V1.1.4','Production','192.168.1.1','APPLY','OK',MAC1,'CMTDC0112255','192.168.2.121','QA','PASS')
    b=new_batch(root,'RUN002','QA',True)
    add_default_verification(b,'V1.1.4','Production','192.168.1.1',MAC1,'CMTDC0112255',
        'QA','PASS',{'MATCH':57,'DIFF':0,'UNKNOWN':0},'hash','Independent default',
        [('nas0_0','vid',7,7,'MATCH')])
    assert len(read_rows(b,3))==1
    assert len(read_rows(a,3))==0
    assert len(read_rows(a,0))==1
    assert len(read_rows(b,0))==0


def test_missing_batch_directory_fail_closed(tmp_path):
    root=tmp_path/'records';root.mkdir()
    (root/'active_batch.json').write_text(json.dumps({'format':1,'active_batch':'GONE'}))
    with pytest.raises(FileNotFoundError):active_batch(root)
