import tempfile
from pathlib import Path
import pytest
from openpyxl import load_workbook, Workbook
from default_verify import compare_defaults, save_baseline, load_baseline
from unified_store import ensure_workbook, add_default_verification,read_rows,workbook_path

BASE={'nas0_0':{'vid':7,'port10ge':0},'nas0_1':{'vid':747},'nas0_2':{'vid':9,'port10ge':1}}

def test_default_compare_pass_fail_unknown():
 assert compare_defaults(BASE,BASE)[0]=='PASS'
 assert compare_defaults(BASE,{**BASE,'nas0_0':{'vid':160,'port10ge':1}})[0]=='FAIL'
 assert compare_defaults(BASE,{**BASE,'nas0_0':{'vid':None,'port10ge':0}})[0]=='VERIFY_INCOMPLETE'

def test_golden_explicit_consent_and_immutability(tmp_path):
 with pytest.raises(ValueError):save_baseline(tmp_path,BASE,'QA',False)
 save_baseline(tmp_path,BASE,'QA',True)
 assert load_baseline(tmp_path)['interfaces']==BASE
 with pytest.raises(FileExistsError):save_baseline(tmp_path,BASE,'QA',True)
 p=tmp_path/'GRG4361_Factory_Default_Golden.json'
 p.write_text(p.read_text().replace('747','748'))
 with pytest.raises(ValueError):load_baseline(tmp_path)

def test_unified_excel_default_history(tmp_path):
 ensure_workbook(tmp_path)
 for expected in ('PASS','FAIL'):
  result,counts,detail=compare_defaults(BASE,BASE if expected=='PASS' else {**BASE,'nas0_0':{'vid':160,'port10ge':1}})
  add_default_verification(tmp_path,'V1.1.1','Engineering','192.168.1.1','3872C0112255','CMTDC0112255','QA',result,counts,'hash','test',detail)
 assert len(read_rows(tmp_path,3))==2
 assert len(read_rows(tmp_path,4))==10
 assert len(read_rows(tmp_path,2))==2
 assert len(load_workbook(workbook_path(tmp_path)).sheetnames)==5

def test_existing_3sheet_upgrade_preserves_rows(tmp_path):
 from unified_store import _write
 from zipfile import ZipFile
 import shutil
 ensure_workbook(tmp_path)
 # Use a known 3-sheet reference if present, otherwise test missing-sheet fallback separately.
 path=workbook_path(tmp_path)
 wb=load_workbook(path)
 for name in ('Default Verification Summary','Default Verification Detail'):del wb[name]
 wb.worksheets[0]['A2']='old-production-record'
 wb.save(path)
 ensure_workbook(tmp_path)
 after=load_workbook(path)
 assert len(after.sheetnames)==5
 assert after.worksheets[0]['A2'].value=='old-production-record'
