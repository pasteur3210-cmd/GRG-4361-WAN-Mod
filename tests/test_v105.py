import tempfile
from pathlib import Path
import pytest
from wan_tool import (check_identity, reserve_ip, ledger_event, read_ledger,
                      allocation_state, build_payload, TARGET)
from router_oqc.wan_config_parser import parse_wan_config_page
from wan_tool import compare_basic,extended_comparison,comparison_summary

def test_real_html_19_readback():
    # Bundled sanitized fixture generated from actual DUT, no credential/token.
    html=(Path(__file__).parent/'fixtures'/'wan_page_sanitized.html').read_text(encoding='utf-8')
    c,_=parse_wan_config_page(html)
    comp=extended_comparison(html,TARGET,compare_basic(c[0],TARGET))
    assert comparison_summary(comp)==('OK',{'MATCH':19,'DIFF':0,'UNKNOWN':0})

def test_identity():
    assert check_identity('00:11:22:AA:BB:CC','CMTD22AABBCC')==('001122AABBCC','CMTD22AABBCC')
    with pytest.raises(ValueError):check_identity('001122AABBCC','CMTD22AABBCE')

def test_unique_allocation():
    with tempfile.TemporaryDirectory() as folder:
        reserve_ip(folder,'001122AABBCC','CMTD22AABBCC','192.168.2.121','192.168.1.1','QA')
        assert Path(folder,'WAN_IP_Allocation.xlsx').exists()
        with pytest.raises(ValueError):
            reserve_ip(folder,'001122AABBDD','CMTD22AABBDD','192.168.2.121','192.168.1.1','QA')
        reserve_ip(folder,'001122AABBDD','CMTD22AABBDD','192.168.2.122','192.168.1.1','QA')
        assert len(read_ledger(folder))==2
        assert allocation_state(read_ledger(folder))['001122AABBDD']['target_ip']=='192.168.2.122'

def test_target_changes_only_local_ip():
    with tempfile.TemporaryDirectory():
        t=dict(TARGET);t['ip']='192.168.2.130'
        data=build_payload(t,'a'*32,'')
        assert ('ip','192.168.2.130') in data
        assert ('multicast_vid','160') in data
        assert sum(k=='chkpt' for k,v in data)==5
        assert all(k!='ip' or v!='192.168.2.121' for k,v in data)
