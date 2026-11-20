import json
from pathlib import Path
from default_verify import install_reference_if_missing,load_baseline
from unified_store import ensure_workbook,add_history,last_wan_apply,add_default_verification,read_rows

def test_bundled_golden_available_and_immutable(tmp_path):
    p=install_reference_if_missing(tmp_path)
    assert p.exists()
    data=load_baseline(tmp_path)
    assert set(data['interfaces']) >= {'nas0_0','nas0_1','nas0_2'}
    before=p.read_bytes()
    assert install_reference_if_missing(tmp_path)==p
    assert p.read_bytes()==before

def test_link_apply_across_separate_calls_and_no_false_link(tmp_path):
    ensure_workbook(tmp_path)
    add_history(tmp_path,'V1.1.3','Production','192.168.1.1','APPLY','OK',
      '1C6499ABE129','CMTD99ABE129','192.168.2.122','QA','PASS')
    assert last_wan_apply(tmp_path,'1c6499abe129','cmtd99abe129')['Target IP']=='192.168.2.122'
    assert last_wan_apply(tmp_path,'1C6499ABE129','CMTDOTHER') is None
    assert last_wan_apply(tmp_path,'3872C0112255','CMTD99ABE129') is None
    add_default_verification(tmp_path,'V1.1.3','Production','192.168.1.1',
        '1C6499ABE129','CMTD99ABE129','QA','PASS',
        {'MATCH':57,'DIFF':0,'UNKNOWN':0},'hash','Linked WAN APPLY', [('nas0_0','vid',7,7,'MATCH')])
    assert len(read_rows(tmp_path,3))==1
    assert len(read_rows(tmp_path,0))==1
