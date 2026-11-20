import copy
from wan_tool import verify_non_target_wans, TRANSFER_LABEL


def fixtures():
    before={
        'nas0_0': {'vid':7, 'port10ge':0},
        'nas0_1': {'vid':747, 'port10ge':0, 'ctype':8},
        'nas0_2': {'vid':9, 'port10ge':1, 'ctype':4},
    }
    after=copy.deepcopy(before)
    after['nas0_0'].update(vid=160,port10ge=1)
    after['nas0_2']['port10ge']=0
    return before,after


def test_exact_transfer_allowed():
    before,after=fixtures()
    assert verify_non_target_wans(before,after)==(True,TRANSFER_LABEL,[])


def test_no_transfer_allowed():
    before,after=fixtures()
    after['nas0_2']['port10ge']=1
    assert verify_non_target_wans(before,after)==(True,'',[])


def test_other_wan_difference_rejected():
    before,after=fixtures()
    after['nas0_2']['vid']=99
    allowed,transfer,errors=verify_non_target_wans(before,after)
    assert not allowed and transfer==TRANSFER_LABEL and 'nas0_2.vid' in errors[0]


def test_nas01_difference_rejected():
    before,after=fixtures()
    after['nas0_1']['ctype']=4
    assert verify_non_target_wans(before,after)[0] is False


def test_wrong_direction_rejected():
    before,after=fixtures()
    before['nas0_2']['port10ge']=0
    assert verify_non_target_wans(before,after)[0] is True # unchanged, no transfer
    after['nas0_2']['port10ge']=1
    assert verify_non_target_wans(before,after)[0] is False


def test_no_target_mapping_rejected():
    before,after=fixtures()
    after['nas0_0']['port10ge']=0
    assert verify_non_target_wans(before,after)[0] is False


def test_missing_interface_rejected():
    before,after=fixtures()
    del after['nas0_1']
    assert verify_non_target_wans(before,after)[0] is False


def test_extra_field_rejected():
    before,after=fixtures()
    after['nas0_2']['newfield']=1
    assert verify_non_target_wans(before,after)[0] is False


def test_real_device_records():
    import json
    from pathlib import Path
    d=Path(__file__).parent/'fixtures'
    before=json.loads((d/'v106_before.json').read_text(encoding='utf-8'))
    after=json.loads((d/'v106_after.json').read_text(encoding='utf-8'))
    assert verify_non_target_wans(before,after)==(True,TRANSFER_LABEL,[])
