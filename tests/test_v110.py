from pathlib import Path

def test_operator_outside_scan_fields():
    source=Path(__file__).resolve().parents[1].joinpath('main.py').read_text(encoding='utf-8')
    assert "operator_ent=ttk.Entry(frm,width=20,textvariable=operator_var,state='readonly',takefocus=0)" in source
    assert "mac_ent.bind('<Return>',mac_scan_complete)" in source
    assert "gpon_ent.bind('<Return>',gpon_scan_complete)" in source
    assert "gpon_ent.focus_set()" in source
    assert "mac_ent.delete(0,'end');gpon_ent.delete(0,'end');mac_ent.focus_set()" in source

def test_release_name_consistency():
    base=Path(__file__).resolve().parents[1]
    assert "VERSION = 'V1.1.3'" in (base/'main.py').read_text()
    assert "GRG4361_WAN_Setting_V1.1.3" in (base/'GRG4361_WAN.spec').read_text()
    assert 'GRG4361_WAN_Setting_V1.1.3' in (base/'.github/workflows/build.yml').read_text()
