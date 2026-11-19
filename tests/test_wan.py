from pathlib import Path
import pytest
from wan_tool import TARGET,validate_target,build_payload,compare_basic
from router_oqc.wan_config_parser import WanConfig

def test_target_valid():validate_target(TARGET)
def test_priority_encoding():
    payload=build_payload(TARGET,'a'*32,'')
    assert ('vprio','1') in payload
    assert ('ipMode','0') in payload
    assert ('ip','192.168.2.121') in payload
    assert ('netmask','255.255.255.0') in payload
    assert len([1 for k,v in payload if k=='chkpt'])==5
    assert payload[-1]==('csrftoken','a'*32)
def test_invalid_subnet():
    d=TARGET.copy();d['netmask']='255.99.0.0'
    with pytest.raises(Exception):validate_target(d)
def test_basic_comparison():
    c=WanConfig(0,'nas0_0',1,1,0,0,1,7,3,0,1,1500,1492,1)
    v=compare_basic(c,TARGET)
    assert not v['vid']['match']
    assert v['cmode']['match']
