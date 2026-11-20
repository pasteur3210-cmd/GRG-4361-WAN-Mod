from pathlib import Path
import tempfile, zipfile, pytest
from unified_store import (ensure_workbook, workbook_path, read_rows, reserve, add_history,
                           add_allocation, ip_state, import_legacy_csv)

def test_single_excel_and_append():
 with tempfile.TemporaryDirectory() as td:
  ensure_workbook(td)
  reserve(td,'Engineering','QA','001122AABBCC','CMTD22AABBCC','192.168.2.121','192.168.1.1')
  add_allocation(td,'Engineering','APPLY','OK','QA','001122AABBCC','CMTD22AABBCC','192.168.2.121','192.168.1.1','transfer')
  add_history(td,'V1.0.8','Engineering','192.168.1.1','APPLY','OK','001122AABBCC','CMTD22AABBCC','192.168.2.121','QA','19/19')
  assert len(read_rows(td,0))==1
  assert len(read_rows(td,1))==2
  assert len(read_rows(td,2))==1
  assert [p.suffix for p in Path(td).iterdir() if p.is_file()] == ['.xlsx']
  with zipfile.ZipFile(workbook_path(td)) as z:
   assert z.testzip() is None
   for i in range(1,4):assert f'xl/worksheets/sheet{i}.xml' in z.namelist()

def test_retest_same_mac_and_block_other_mac():
 with tempfile.TemporaryDirectory() as td:
  ensure_workbook(td)
  for _ in range(2):reserve(td,'Engineering','QA','001122AABBCC','CMTD22AABBCC','192.168.2.121','192.168.1.1')
  assert len(read_rows(td,1))==2
  with pytest.raises(ValueError,match='collision'):
   reserve(td,'Engineering','QA','001122AABBDD','CMTD22AABBDD','192.168.2.121','192.168.1.1')
  with pytest.raises(ValueError,match='already assigned'):
   reserve(td,'Production','QA','001122AABBDD','CMTD22AABBDD','192.168.2.121','192.168.1.1')

def test_import_legacy_and_no_reimport_duplicate():
 with tempfile.TemporaryDirectory() as td:
  src=Path(td)/'old';src.mkdir()
  (src/'WAN_IP_Allocation.csv').write_text('time,event,result,operator,device_mac,gpon_sn,target_ip,router_ip,notes\n2026-01-01,APPLY,OK,QA,001122AABBCC,CMTD22AABBCC,192.168.2.121,192.168.1.1,old\n')
  folder=Path(td)/'new';ensure_workbook(folder)
  assert import_legacy_csv(folder,src/'WAN_IP_Allocation.csv')==1
  assert import_legacy_csv(folder,src/'WAN_IP_Allocation.csv')==0
  assert ip_state(folder)['001122AABBCC']['Target IP']=='192.168.2.121'
  assert not any(x.suffix=='.csv' for x in folder.iterdir())
