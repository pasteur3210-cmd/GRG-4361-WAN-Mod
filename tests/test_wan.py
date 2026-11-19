from pathlib import Path
import pytest
from wan_tool import TARGET,validate_target,build_payload,compare_basic,extended_comparison
from router_oqc.wan_config_parser import WanConfig

def test_target_valid():validate_target(TARGET)
def test_browser_fields_order():
    from wan_tool import BROWSER_PAYLOAD
    assert ('ctypeForBridge','2') in BROWSER_PAYLOAD
    assert ('lst','nas0_0') in BROWSER_PAYLOAD
    assert ('itfGroup','16') in BROWSER_PAYLOAD
    assert ('qosEnabled','ON') in BROWSER_PAYLOAD
    ports=[v for k,v in BROWSER_PAYLOAD if k=='chkpt']
    assert ports==['','','','','on']
    assert ('ipMode','0') in BROWSER_PAYLOAD
    assert ('netmask','255.255.255.0') in BROWSER_PAYLOAD

def test_checksum_gate():
    from wan_tool import browser_payload_safety_check, BROWSER_RECORDED_FLAG, BROWSER_PAYLOAD
    from router_oqc.post_security import post_security_flag
    if post_security_flag(BROWSER_PAYLOAD)!=BROWSER_RECORDED_FLAG:
        with pytest.raises(ValueError,match='checksum not verified'):
            build_payload(TARGET,'a'*32,'')
    else:
        assert browser_payload_safety_check()
        assert build_payload(TARGET,'a'*32,'')[-1]==('csrftoken','a'*32)

def test_invalid_subnet():
    d=TARGET.copy();d['netmask']='255.99.0.0'
    with pytest.raises(Exception):validate_target(d)
def test_basic_comparison():
    c=WanConfig(0,'nas0_0',1,1,0,0,1,7,3,0,1,1500,1492,1)
    v=compare_basic(c,TARGET)
    assert not v['vid']['match']
    assert v['cmode']['match']

def test_unknown_readback_not_pass():
    c=WanConfig(0,'nas0_0',2,1,3,0,1,160,1,0,1,1500,1492,1)
    result=extended_comparison('',TARGET,compare_basic(c,TARGET))
    assert result['vid']['status']=='MATCH'
    assert result['ip']['status']=='DIFF'  # real parsed value differs
    assert result['br']['status']=='MATCH'
    assert result['port10ge']['status']=='DIFF'


def test_multicast_vlan_writing():
    from wan_tool import BROWSER_PAYLOAD, browser_payload_safety_check
    from router_oqc.post_security import post_security_flag
    assert ('multicast_vid', '') in BROWSER_PAYLOAD  # historical capture stays immutable
    browser_payload_safety_check()
    payload = build_payload(TARGET, 'a'*32, '')
    assert [v for k,v in payload if k=='multicast_vid'] == ['160']
    bare = [(k,v) for k,v in payload if k not in ('postSecurityFlag','csrftoken')]
    assert [v for k,v in payload if k=='postSecurityFlag'] == [str(post_security_flag(bare))]
    assert [v for k,v in payload if k=='chkpt'] == ['', '', '', '', 'on']

def test_multicast_vlan_unknown_in_readback():
    c=WanConfig(0,'nas0_0',2,1,3,0,1,160,1,0,1,1500,1492,1)
    r=extended_comparison('', TARGET, compare_basic(c,TARGET))
    assert r['multicast_vid']['status']=='DIFF'  # value 0 differs from target 160

def test_multicast_vlan_range():
    for bad in [0,4096,-1,'160']:
        d=TARGET.copy();d['multicast_vid']=bad
        with pytest.raises(ValueError,match='Multicast VLAN'):
            validate_target(d)
