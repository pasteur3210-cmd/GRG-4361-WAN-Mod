"""Single-XLSX, append-only WAN records. Pure stdlib OOXML; no CSV sidecar.

One PC / one EXE directory. Uses a file lock and atomic replace; do not open
workbook in Excel while a write is in progress.
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager
from xml.etree import ElementTree as ET
import csv, io, json, os, tempfile, time, zipfile, re

FILE = 'GRG4361_WAN_Master_Record.xlsx'
SHEETS = ['WAN Setting Master Record', 'IP Allocation', 'Test History', 'Default Verification Summary', 'Default Verification Detail']
HEADERS = [
 ['Time','Version','Mode','Router IP','Stage','Result','MAC','GPON SN','Target IP','Operator','Details','Before JSON','After JSON'],
 ['Time','Event','Result','Mode','Operator','MAC','GPON SN','Target IP','Router IP','Notes'],
 ['Time','Version','Mode','Router IP','Stage','Result','MAC','GPON SN','Target IP','Operator','Notes'],
 ['Time','Version','Mode','Router IP','MAC','GPON SN','Operator','Result','MATCH','DIFF','UNKNOWN','Golden SHA256','Details'],
 ['Time','MAC','GPON SN','Interface','Field','Expected','Actual','Result','Golden SHA256']]
NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
PKG='http://schemas.openxmlformats.org/package/2006/relationships'
RNS='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
CT='http://schemas.openxmlformats.org/package/2006/content-types'
ET.register_namespace('',NS)
ET.register_namespace('r',RNS)

def workbook_path(folder):return Path(folder)/FILE

def _col(n):
 s=''
 while n:n,r=divmod(n-1,26);s=chr(65+r)+s
 return s

def _sheet_xml(rows):
 root=ET.Element(f'{{{NS}}}worksheet')
 views=ET.SubElement(root,f'{{{NS}}}sheetViews');ET.SubElement(views,f'{{{NS}}}sheetView',{'workbookViewId':'0','showGridLines':'0'})
 cols=ET.SubElement(root,f'{{{NS}}}cols')
 for idx,width in enumerate(([23,15,16,20,18,20,20,20,22,20,60,50,50] if len(rows[0])==13 else [23,18,20,15,20,20,20,22,20,60]),1):
  ET.SubElement(cols,f'{{{NS}}}col',{'min':str(idx),'max':str(idx),'width':str(width),'customWidth':'1'})
 data=ET.SubElement(root,f'{{{NS}}}sheetData')
 for rno,row in enumerate(rows,1):
  r=ET.SubElement(data,f'{{{NS}}}row',{'r':str(rno),'ht':'24' if rno==1 else '17','customHeight':'1' if rno==1 else '0'})
  for cno,value in enumerate(row,1):
   if value is None:value=''
   c=ET.SubElement(r,f'{{{NS}}}c',{'r':_col(cno)+str(rno),'t':'inlineStr','s':'1' if rno==1 else '0'})
   inline=ET.SubElement(c,f'{{{NS}}}is');ET.SubElement(inline,f'{{{NS}}}t').text=str(value)
 ET.SubElement(root,f'{{{NS}}}autoFilter',{'ref':f'A1:{_col(len(rows[0]))}{len(rows)}'})
 return ET.tostring(root,encoding='utf-8',xml_declaration=True)

def _write(path,data):
 path.parent.mkdir(parents=True,exist_ok=True)
 fd,tmp=tempfile.mkstemp(prefix='.wan_xlsx_',suffix='.tmp',dir=path.parent);os.close(fd)
 try:
  template=Path(__file__).resolve().parent/'template.xlsx'
  with zipfile.ZipFile(template) as source, zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED) as dest:
   for item in source.infolist():
    match=re.fullmatch(r'xl/worksheets/sheet([1-5])\.xml',item.filename)
    content=_sheet_xml(data[int(match.group(1))-1]) if match else source.read(item.filename)
    dest.writestr(item.filename,content)
  os.replace(tmp,path)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)

def _read(path):
 if not path.exists():return [[list(h)] for h in HEADERS]
 data=[]
 with zipfile.ZipFile(path) as z:
  shared=[]
  if 'xl/sharedStrings.xml' in z.namelist():
   sr=ET.fromstring(z.read('xl/sharedStrings.xml'))
   shared=[''.join(t.text or '' for t in x.iter(f'{{{NS}}}t')) for x in sr.findall(f'{{{NS}}}si')]
  for i in range(1,len(SHEETS)+1):
   if f'xl/worksheets/sheet{i}.xml' not in z.namelist():
    data.append([list(HEADERS[i-1])]);continue
   root=ET.fromstring(z.read(f'xl/worksheets/sheet{i}.xml'))
   sheet=[]
   for row in root.findall(f'.//{{{NS}}}sheetData/{{{NS}}}row'):
    values=['']*len(HEADERS[i-1])
    for c in row.findall(f'{{{NS}}}c'):
     ref=c.get('r','');letters=re.match('[A-Z]+',ref)
     if not letters:continue
     idx=0
     for ch in letters.group():idx=idx*26+ord(ch)-64
     if idx>len(values):continue
     val=c.find(f'{{{NS}}}v')
     if c.get('t')=='inlineStr':value=''.join(t.text or '' for t in c.iter(f'{{{NS}}}t'))
     elif c.get('t')=='s' and val is not None:value=shared[int(val.text)]
     else:value=val.text if val is not None else ''
     values[idx-1]=value or ''
    sheet.append(values)
   data.append(sheet or [list(HEADERS[i-1])])
 return data

@contextmanager
def locked(folder):
 folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
 lock=folder/'.wan_master.lock';fd=None
 for _ in range(60):
  try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);break
  except FileExistsError:time.sleep(.1)
 if fd is None:raise RuntimeError('Excel record is locked; close other application instances')
 os.close(fd)
 try:yield
 finally:lock.unlink(missing_ok=True)

def add_row(folder,index,row):
 with locked(folder):
  path=workbook_path(folder);data=_read(path)
  if len(row)!=len(HEADERS[index]):raise ValueError('Record schema mismatch')
  data[index].append([str(v) if v is not None else '' for v in row]);_write(path,data)
 return row

def read_rows(folder,index):
 return [dict(zip(HEADERS[index],r)) for r in _read(workbook_path(folder))[index][1:]]

def ensure_workbook(folder):
 with locked(folder):
  path=workbook_path(folder)
  if not path.exists():_write(path,[[list(h)] for h in HEADERS])
  else:
   existing=_read(path)
   with zipfile.ZipFile(path) as z:
    if f'xl/worksheets/sheet{len(SHEETS)}.xml' not in z.namelist():_write(path,existing)
 return workbook_path(folder)

def ip_state(folder):
 out={}
 for row in read_rows(folder,1):
  mac=row.get('MAC','')
  if mac:out[mac]=row
 return out

ACTIVE={'RESERVED','HOLD','OK','VERIFY_INCOMPLETE','MANUAL_OK'}

def reserve(folder,mode,operator,mac,gpon,ip,router):
 if not re.fullmatch(r'192\.168\.2\.(12[1-9]|130)',ip):raise ValueError('Target IP must be 192.168.2.121~130')
 with locked(folder):
  path=workbook_path(folder);data=_read(path)
  state={r[5]:r for r in data[1][1:] if r[5]}
  if mode=='Production':
   for other,r in state.items():
    if r[2] in ACTIVE and other!=mac and r[7]==ip:raise ValueError(f'IP {ip} already assigned to MAC {other}')
    if r[2] in ACTIVE and other!=mac and r[6]==gpon:raise ValueError('GPON SN already assigned')
   prev=state.get(mac)
   if prev and prev[2] in ACTIVE and prev[7]!=ip:raise ValueError(f'MAC {mac} already assigned to {prev[7]}')
  else:
   for other,r in state.items():
    if other!=mac and r[2] in ACTIVE and r[7]==ip:
     # Physical collision cannot be allowed even in regression mode.
     raise ValueError(f'Engineering IP collision: {ip} is already recorded for MAC {other}. Use another IP or a separate isolated test workspace.')
  data[1].append([datetime.now().isoformat(timespec='seconds'),'RESERVE','RESERVED',mode,operator,mac,gpon,ip,router,'Before WAN write'])
  _write(path,data)

def add_allocation(folder,mode,event,result,operator,mac,gpon,ip,router,notes):
 return add_row(folder,1,[datetime.now().isoformat(timespec='seconds'),event,result,mode,operator,mac,gpon,ip,router,notes])

def add_history(folder,version,mode,router,stage,result,mac,gpon,ip,operator,notes,before='',after=''):
 timestamp=datetime.now().isoformat(timespec='seconds')
 with locked(folder):
  path=workbook_path(folder);data=_read(path)
  if stage == 'APPLY':
   data[0].append([timestamp,version,mode,router,stage,result,mac,gpon,ip,operator,notes,before,after])
  data[2].append([timestamp,version,mode,router,stage,result,mac,gpon,ip,operator,notes])
  _write(path,data)

def import_legacy_csv(folder,path,mode='Production'):
 path=Path(path)
 if path.name!='WAN_IP_Allocation.csv':raise ValueError('Choose legacy WAN_IP_Allocation.csv')
 with path.open('r',encoding='utf-8-sig',newline='') as f:items=list(csv.DictReader(f))
 with locked(folder):
  dest=workbook_path(folder);data=_read(dest)
  existing={tuple(r) for r in data[1][1:]};added=0
  current={r[5]:r for r in data[1][1:] if r[5]}
  for item in items:
   row=[item.get('time',''),item.get('event',''),item.get('result',''),mode,item.get('operator',''),item.get('device_mac',''),item.get('gpon_sn',''),item.get('target_ip',''),item.get('router_ip',''),item.get('notes','')]
   if not row[5] or not row[7]:raise ValueError('Legacy row missing MAC or IP')
   if tuple(row) in existing:continue
   if mode=='Production' and row[2] in ACTIVE:
    for mac,other in current.items():
     if mac!=row[5] and other[2] in ACTIVE and other[7]==row[7]:raise ValueError(f'Conflicting IP {row[7]}: {mac} and {row[5]}')
   data[1].append(row);existing.add(tuple(row));current[row[5]]=row;added+=1
  _write(dest,data)
 return added


def add_default_verification(folder, version, mode, router, mac, gpon, operator, result, counts, fingerprint, details, fields):
    """Append one immutable summary + individual field comparisons in one atomic write."""
    stamp=datetime.now().isoformat(timespec='seconds')
    with locked(folder):
        path=workbook_path(folder);data=_read(path)
        data[3].append([stamp,version,mode,router,mac,gpon,operator,result,str(counts['MATCH']),str(counts['DIFF']),str(counts['UNKNOWN']),fingerprint,details])
        for interface,field,expected,actual,status in fields:
            data[4].append([stamp,mac,gpon,interface,field,str(expected),str(actual),status,fingerprint])
        data[2].append([stamp,version,mode,router,'DEFAULT_VERIFY',result,mac,gpon,'',operator,details])
        _write(path,data)
