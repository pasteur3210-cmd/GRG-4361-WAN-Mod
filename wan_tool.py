from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
from html import escape
from bs4 import BeautifulSoup
import csv, json, ipaddress, re, time, os, uuid, contextlib, shutil
from router_oqc.client import RouterClient, RouterError
from router_oqc.wan_config_client import read_wan, BRIDGE_FIELDS
from router_oqc.post_security import post_security_flag
from unified_store import add_history, reserve as xlsx_reserve, add_allocation as xlsx_allocation

TARGET = {'interface':'nas0_0','vlan':1,'vid':160,'vprio':1,'cmode':1,
          'br':1,'brmode':3,'napt':0,'enable':1,'ctype':2,'mtu':1500,
          'multicast_vid':160,'ipMode':0,'ip':'192.168.2.121','remoteIp':'192.168.2.100',
          'netmask':'255.255.255.0','dnsMode':0,'v6TunnelType':0,'port10ge':1}
RECORD_FIELDS=['timestamp','router','stage','result','details','before','after']


def validate_target(t):
    for key in ('ip','remoteIp','netmask'):
        ipaddress.IPv4Address(t[key])
    ipaddress.IPv4Network('0.0.0.0/'+t['netmask'])
    if ipaddress.IPv4Address(t['ip']) not in ipaddress.IPv4Network(t['ip']+'/'+t['netmask'], strict=False):
        raise ValueError('IP / Subnet Mask inconsistent')
    if t['vid']<1 or t['vid']>4094: raise ValueError('VLAN out of range')
    if not isinstance(t.get('multicast_vid'), int) or not 1 <= t['multicast_vid'] <= 4095: raise ValueError('Multicast VLAN out of range')
    if t['interface']!='nas0_0': raise ValueError('Only nas0_0 is supported')


def config_values(conf):
    # Source of truth: DUT GET /admin/multi_wan_generic.asp, links[] initialization.
    # Never derive the current settings from target or submitted POST.
    return {'interface':conf.name, 'vlan':conf.vlan, 'vid':conf.vid,
        'vprio':conf.vprio,'cmode':conf.cmode,'brmode':conf.brmode,
        'napt':conf.napt, 'enable':conf.enable,'ctype':conf.applicationtype,
        'mtu':conf.mtu, 'br':int(conf.cmode != 0 and conf.brmode not in (0,2)),
        'multicast_vid':conf.mVid, 'ipMode':conf.ipDhcp,
        'ip':conf.ipAddr, 'remoteIp':conf.remoteIpAddr,
        'netmask':conf.netMask, 'dnsMode':conf.dnsMode,
        'v6TunnelType':conf.v6TunnelType,
        'port10ge':int(bool(conf.itfGroup & 16))}

def compare_basic(conf,target):
    curr=config_values(conf)
    # WAN parser has no independent bridge enabled field. brmode is only a partial proxy.
    return {k:{'current':curr.get(k), 'target':target[k], 'match':curr.get(k)==target[k]}
        for k in curr if k in target}


def find_live_static_values(html):
    # The copied form itself may not preserve JS-assigned values; never assume empty means DHCP.
    soup=BeautifulSoup(html,'html.parser')
    form=soup.find('form',attrs={'name':'ethwan'})
    if not form: return {}
    out={}
    for name in ('ipMode','ip','remoteIp','netmask','dnsMode'):
        nodes=form.find_all('input',attrs={'name':name})
        if not nodes:continue
        if nodes[0].get('type')=='radio':
            checked=[x.get('value') for x in nodes if x.has_attr('checked')]
            if checked:out[name]=checked[0]
        else:
            if nodes[0].has_attr('value') and not nodes[0].has_attr('disabled'):
                out[name]=nodes[0].get('value')
    return out


def comparison_summary(comparison):
    counts = {key: sum(item['status'] == key for item in comparison.values())
              for key in ('MATCH', 'DIFF', 'UNKNOWN')}
    if counts['DIFF']:
        result = 'NG'
    elif counts['UNKNOWN']:
        result = 'VERIFY_INCOMPLETE'
    elif comparison:
        result = 'OK'
    else:
        result = 'VERIFY_INCOMPLETE'
    return result, counts


def extended_comparison(html, target, basic):
    # The parser now reads all 19 fields directly from DUT links[] data.
    # Missing values must remain UNKNOWN, never be inferred from submitted values.
    out={}
    for key in target:
        if key not in basic:
            out[key]={'current':None,'target':target[key],'status':'UNKNOWN'}
        else:
            val=basic[key]['current']
            out[key]={'current':val,'target':target[key],
                      'status':'UNKNOWN' if val is None else ('MATCH' if val==target[key] else 'DIFF')}
    return out


# Browser-captured successful target submission (2026-11-19).  Empty fields
# are retained. Tokens/flags excluded: generated per transaction.
# Order matters, especially the five chkpt entries.
BROWSER_PAYLOAD = [
    ('v6TunnelRv4IP',''),('lkname','0'),('vlan','ON'),('vid','160'),('vprio','1'),
    ('multicast_vid',''),('adslConnectionMode','1'),('br','ON'),('brmode','3'),
    ('chEnable','1'),('ctype','2'),('ctypeForBridge','2'),('mtu','1500'),
    ('mtu_pppoe','1500'),('maccloneaddr',''),('droute','0'),('IpProtocolType','1'),
    ('auth','0'),('acName',''),('serviceName',''),('ipMode','0'),
    ('ip','192.168.2.121'),('remoteIp','192.168.2.100'),
    ('netmask','255.255.255.0'),('dns1',''),('dns2',''),('opt60_val',''),
    ('iaid','0'),('duid_type','1'),('duid_ent_num','0'),('duid_id',''),
    ('manufacturer',''),('product_class',''),('model_name',''),('serial_num',''),
    ('v6TunnelType','0'),('SixrdBRv4IP',''),('SixrdIPv4MaskLen',''),
    ('SixrdPrefix',''),('SixrdPrefixLen',''),('Ipv6Dns16rd',''),('Ipv6Dns26rd',''),
    ('Ipv6Addr6in4',''),('Ipv6PrefixLen6in4',''),('Ipv6Gateway6in4',''),
    ('v6TunnelRv4IP6in4',''),('dnsV6Mode6in4','0'),('Ipv6Dns16in4',''),
    ('Ipv6Dns26in4',''),('v6TunnelRv4IP6to4',''),('Ipv6Dns16to4',''),
    ('Ipv6Dns26to4',''),('AddrMode','1'),('Ipv6Addr',''),
    ('Ipv6PrefixLen',''),('Ipv6Gateway',''),('iapd','ON'),('dnsV6Mode','1'),
    ('napt_v6','0'),('s4over6Type','0'),('dslite_aftr_hostname',''),
    ('chkpt',''),('chkpt',''),('chkpt',''),('chkpt',''),('chkpt','on'),
    ('submit-url','/admin/multi_wan_generic.asp'),('lst','nas0_0'),
    ('encodePppUserName',''),('encodePppPassword',''),('qosEnabled','ON'),
    ('apply','Apply Changes'),('itfGroup','16')]
BROWSER_RECORDED_FLAG = 46002

def browser_payload_safety_check():
    """Validate recorded form and flag generation before writing.

    Explicitly fail closed if our checksum algorithm cannot reproduce the
    captured legitimate browser submission. Never send a guessed checksum.
    """
    actual=post_security_flag(BROWSER_PAYLOAD)
    if actual!=BROWSER_RECORDED_FLAG:
        raise ValueError('Security checksum not verified: generated %s, browser %s. '
            'Write disabled until the algorithm/encoding is confirmed.' %
            (actual,BROWSER_RECORDED_FLAG))
    return True

def build_payload(t,token,source_html):
    validate_target(t)
    if not re.fullmatch(r'[A-Za-z0-9]{16,128}',token):
        raise ValueError('Invalid CSRF token format')
    # Refuse to write if the captured browser checksum is not reproducible.
    browser_payload_safety_check()
    update={'vid':str(t['vid']),'vprio':str(t['vprio']), 'multicast_vid':str(t['multicast_vid']),
        'adslConnectionMode':str(t['cmode']),'brmode':str(t['brmode']),
        'ctype':str(t['ctype']),'ctypeForBridge':str(t['ctype']),
        'mtu':str(t['mtu']),'ipMode':str(t['ipMode']),
        'ip':t['ip'],'remoteIp':t['remoteIp'],'netmask':t['netmask'],
        'v6TunnelType':str(t['v6TunnelType'])}
    fields=[(k,update.get(k,v)) for k,v in BROWSER_PAYLOAD]
    if len([1 for k,_ in fields if k=='chkpt'])!=5:raise ValueError('Invalid port mapping layout')
    names=[k for k,_ in fields if k!='chkpt']
    if len(names)!=len(set(names)):raise ValueError('Duplicate scalar POST field')
    return fields+[('postSecurityFlag',str(post_security_flag(fields))),('csrftoken',token)]

def ensure_target_device(configs):
    candidates=[x for x in configs if x.name=='nas0_0']
    if len(candidates)!=1:raise ValueError('Expected exactly one nas0_0 interface')
    return candidates[0]


# Only the known LAN_1 (10GE) migration from nas0_2 to nas0_0 is allowed.
# All other fields on all non-target WANs remain strictly protected.
TRANSFER_LABEL = 'nas0_2 -> nas0_0 (LAN_1 10GE)'

def verify_non_target_wans(before, after):
    """Return (allowed, transfer_label, violations), checking complete WAN snapshots.

    Missing/new interfaces are violations. Never allow unrelated changes.
    The one permitted change is nas0_2.port10ge 1 -> 0, only when
    nas0_0.port10ge is 1 after the operation.
    """
    violations = []
    transfer = ''
    before_names = set(before) - {'nas0_0'}
    after_names = set(after) - {'nas0_0'}
    if before_names != after_names:
        violations.append('Non-target WAN interfaces changed: before=%s after=%s' %
                          (sorted(before_names), sorted(after_names)))
    target_port_ok = after.get('nas0_0', {}).get('port10ge') == 1
    for name in sorted(before_names | after_names):
        if name not in before or name not in after:
            continue
        prior, current = before[name], after[name]
        for key in sorted(set(prior) | set(current)):
            old, new = prior.get(key), current.get(key)
            if key in prior and key in current and old == new:
                continue
            if (name == 'nas0_2' and key == 'port10ge'
                    and key in prior and key in current
                    and old == 1 and new == 0 and target_port_ok):
                transfer = TRANSFER_LABEL
                continue
            violations.append('%s.%s: %r -> %r' % (name, key, old, new))
    return not violations, transfer, violations


def write_record(folder,router,stage,result,details,before=None,after=None):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    line={'timestamp':datetime.now().isoformat(timespec='seconds'),'router':router,
          'stage':stage,'result':result,'details':details,
          'before':json.dumps(before or {},ensure_ascii=False),
          'after':json.dumps(after or {},ensure_ascii=False)}
    path=folder/'WAN_Master_Record.csv'
    with path.open('a',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=RECORD_FIELDS)
        if f.tell()==0:w.writeheader()
        w.writerow(line)
    # Append cumulative Excel master record for factory-style reporting.
    from openpyxl import Workbook, load_workbook
    xlsx=folder/'WAN_Master_Record.xlsx'
    if xlsx.exists():
        wb=load_workbook(xlsx); ws=wb.active
    else:
        wb=Workbook();ws=wb.active;ws.title='WAN Master Record';ws.append(RECORD_FIELDS)
        ws.freeze_panes='A2';ws.auto_filter.ref='A1:G1'
        for col,width in {'A':22,'B':20,'C':16,'D':20,'E':66,'F':55,'G':55}.items():ws.column_dimensions[col].width=width
    ws.append([line[k] for k in RECORD_FIELDS]);wb.save(xlsx)
    with (folder/'execution.log').open('a',encoding='utf-8') as f:
        f.write(f"{line['timestamp']} {stage} {result} {details}\n")
    return line


class WanSession:
    def __init__(self,host,username,password,output_dir='records',target_ip='192.168.2.121',mac='',gpon_sn='',operator='',mode='Engineering'):
        self.mode=mode
        self.host=host.strip();self.client=RouterClient(self.host,protocol='http',timeout=12)
        self.username=username;self.password=password;self.output_dir=Path(output_dir)
        self.before=None;self.token=None;self.html=None;self.before_wan=None
        self.target=dict(TARGET); self.target['ip']=target_ip
        self.mac=normalize_mac(mac) if mac else '';self.gpon_sn=re.sub(r'[^0-9A-Za-z]','',gpon_sn).upper() if gpon_sn else ''
        self.operator=operator.strip();self.lease_id=None

    def record(self,stage,result,details,before=None,after=None):
        add_history(self.output_dir,'V1.1.4',self.mode,self.host,stage,result,self.mac,self.gpon_sn,self.target['ip'],self.operator,details,json.dumps(before or {},ensure_ascii=False),json.dumps(after or {},ensure_ascii=False))
        with (self.output_dir/'execution.log').open('a',encoding='utf-8') as f:f.write(f'{datetime.now().isoformat()} {stage} {result} {details}\n')

    def close(self):self.client.close()

    def read(self):
        self.client.login(self.username,self.password)
        configs,token,html=read_wan(self.client)
        wan=ensure_target_device(configs)
        self.before=configs;self.before_wan=wan;self.token=token;self.html=html
        self.output_dir.mkdir(parents=True,exist_ok=True)
        self.snapshot_before={c.name:config_values(c) for c in configs}
        # Never log active CSRF tokens or credentials.
        (self.output_dir/'before.json').write_text(json.dumps(self.snapshot_before,indent=2,ensure_ascii=False),encoding='utf-8')
        self.comparison=extended_comparison(html,self.target,compare_basic(wan,self.target))
        read_result, counts = comparison_summary(self.comparison)
        self.record('READ',('READY_TO_APPLY' if read_result == 'NG' else 'ALREADY_CONFIGURED' if read_result == 'OK' else read_result),'Read/Compare: '+str(counts),self.snapshot_before)
        (self.output_dir/'read_comparison.json').write_text(json.dumps(self.comparison,indent=2,ensure_ascii=False),encoding='utf-8')
        return self.comparison

    def apply_experimental(self,confirmation):
        if confirmation!='APPLY nas0_0':raise ValueError('Explicit confirmation required')
        if not self.before_wan or not self.html:raise ValueError('Read WAN first')
        # Reserve this IP atomically for this identity before any device write.
        # re-read before modification and prohibit changes since initial snapshot
        configs,token,html=read_wan(self.client)
        if {c.name:config_values(c) for c in configs}!=self.snapshot_before:
            raise ValueError('WAN settings changed since snapshot. Read again.')
        fields=build_payload(self.target,token,html)  # fails closed until checksum is verified
        xlsx_reserve(self.output_dir,self.mode,self.operator,self.mac,self.gpon_sn,self.target['ip'],self.host)
        # Important: requests accepts a tuple list; its fallback raw transport uses urlencode too.
        # Store only redacted payload to aid verification without secrets.
        sanitized=[(k,'[REDACTED]' if k in ('csrftoken','postSecurityFlag') else v) for k,v in fields]
        (self.output_dir/'payload_candidate.json').write_text(json.dumps(sanitized,indent=2),encoding='utf-8')
        try:
            response=self.client._post('boaform/admin/formWanEth',data=fields,
                allow_redirects=True,headers={'Referer':urljoin(self.client.base_url,'admin/multi_wan_generic.asp')})
            if response.status_code!=200 or 'Change setting successfully' not in response.text:
                raise RuntimeError('HTTP/response did not confirm successful write')
            # Read back basic config; STATIC IP and Port Mapping cannot be verified by old parser.
            time.sleep(2)
            new_configs,new_token,new_html=read_wan(self.client)
            after={c.name:config_values(c) for c in new_configs}
            protected, transfer, violations = verify_non_target_wans(self.snapshot_before, after)
            basic=extended_comparison(new_html,self.target,compare_basic(ensure_target_device(new_configs),self.target))
            statuses=[v['status'] for v in basic.values()]
            target_bad = 'DIFF' in statuses
            target_unknown = 'UNKNOWN' in statuses
            result = ('FAIL' if (target_bad or not protected)
                      else 'VERIFY_INCOMPLETE' if target_unknown else 'OK')
            if not protected:
                missing='Non-target WAN changes: ' + '; '.join(violations)
            elif target_bad:
                missing='Target WAN setting mismatch: ' + ', '.join(k for k,v in basic.items() if v['status']=='DIFF')
            elif target_unknown:
                missing='Target WAN readback incomplete: ' + ', '.join(k for k,v in basic.items() if v['status']=='UNKNOWN')
            else:
                missing='All 19 target settings verified'
            if transfer:
                missing += '; Allowed Port Mapping Transfer: ' + transfer
            self.record('APPLY',result,missing,self.snapshot_before,after)
            (self.output_dir/'after.json').write_text(json.dumps(after,indent=2),encoding='utf-8')
            (self.output_dir/'after_comparison.json').write_text(json.dumps(basic,indent=2,ensure_ascii=False),encoding='utf-8')
            xlsx_allocation(self.output_dir,self.mode,'APPLY',('HOLD' if result=='FAIL' else result),self.operator,self.mac,self.gpon_sn,self.target['ip'],self.host,missing)
            return result,missing,basic
        except Exception as exc:
            self.record('APPLY','FAIL',f'{type(exc).__name__}: {exc}',self.snapshot_before)
            xlsx_allocation(self.output_dir,self.mode,'APPLY','HOLD',self.operator,self.mac,self.gpon_sn,self.target['ip'],self.host,'UNCERTAIN WRITE / manual review required: '+str(exc))
            raise


def save_manual_review(folder, host, comparison, confirmed, operator, notes,mac='',gpon='',ip='',mode='Engineering'):
    """Separate human inspection from automatic validation. Never turn UNKNOWN into auto MATCH."""
    if not isinstance(confirmed,bool):
        raise ValueError('Explicit human review decision required')
    if not operator.strip():
        raise ValueError('Operator is required')
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    automatic, counts = comparison_summary(comparison)
    outcome='MANUAL_OK' if confirmed and counts['DIFF']==0 else 'MANUAL_NG'
    record={'timestamp':datetime.now().isoformat(timespec='seconds'),
            'host':host,'operator':operator.strip(),'manual_result':outcome,
            'automatic_result':automatic,'counts':counts,'notes':notes.strip(),
            'scope':'Web GUI human confirmation only; automatic UNKNOWN remains UNKNOWN'}
    with (folder/'manual_reviews.jsonl').open('a',encoding='utf-8') as f:
        f.write(json.dumps(record,ensure_ascii=False)+'\n')
    add_history(folder,'V1.0.9',mode,host,'MANUAL_REVIEW',outcome,mac,gpon,ip,operator.strip(),'Auto='+automatic+'; '+notes.strip())
    return record


# Stable data path, independent of EXE location and working directory.
def stable_records_dir():
    base=os.environ.get('LOCALAPPDATA') or str(Path.home()/'.local'/'share')
    return Path(base)/'GRG4361_WAN_Setting'/'records'


def ledger_initialized(folder):
    return (Path(folder)/'WAN_IP_Allocation.csv').exists() and (Path(folder)/'WAN_IP_Allocation.csv').stat().st_size>0


def initialize_empty_ledger(folder):
    """Explicit operator approval is required before a new, empty ledger is created."""
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    with ledger_lock(folder):
        path=folder/'WAN_IP_Allocation.csv'
        if path.exists():return False
        with path.open('x',newline='',encoding='utf-8-sig') as out:
            csv.DictWriter(out,fieldnames=LEDGER_FIELDS).writeheader()
    export_ledger_excel(folder)
    return True


def import_legacy_ledger(folder, source):
    """Merge old ledger transaction history; reject any cross-MAC active IP collision."""
    folder=Path(folder);source=Path(source)
    if source.name!='WAN_IP_Allocation.csv':raise ValueError('Select WAN_IP_Allocation.csv from previous records folder')
    if not source.exists():raise FileNotFoundError(source)
    imported=read_ledger(source.parent)
    if not imported:raise ValueError('Legacy ledger is empty')
    if any(not row.get('device_mac') or not row.get('target_ip') for row in imported):
        raise ValueError('Legacy CSV has missing identity / IP fields')
    with ledger_lock(folder):
        existing=read_ledger(folder)
        # Deduplicate exact events. Reconcile active allocations across all logs.
        unique_existing={tuple(row.get(k,'') for k in LEDGER_FIELDS) for row in existing}
        additions=[row for row in imported if tuple(row.get(k,'') for k in LEDGER_FIELDS) not in unique_existing]
        combined=existing+additions
        active=allocation_state(combined)
        ip_owner={}
        for mac,row in active.items():
            if row.get('result') in ('RESERVED','OK','VERIFY_INCOMPLETE','MANUAL_OK','HOLD'):
                ip=row.get('target_ip')
                if ip in ip_owner and ip_owner[ip]!=mac:
                    raise ValueError('Conflicting historical IP assignment '+ip+' for '+ip_owner[ip]+' and '+mac+'; resolve manually')
                ip_owner[ip]=mac
        dest=folder/'WAN_IP_Allocation.csv';dest.parent.mkdir(parents=True,exist_ok=True)
        # No change to existing history until all conflicts are checked.
        if additions:
            with dest.open('a',encoding='utf-8-sig',newline='') as out:
                w=csv.DictWriter(out,fieldnames=LEDGER_FIELDS)
                if out.tell()==0:w.writeheader()
                for row in additions:w.writerow({k:row.get(k,'') for k in LEDGER_FIELDS})
                out.flush();os.fsync(out.fileno())
    export_ledger_excel(folder)
    return len(additions)


# Persistent per-device IP ledger. Source of truth is CSV; Xlsx is a derived report.
LEDGER_FIELDS=['time','event','result','operator','device_mac','gpon_sn','target_ip','router_ip','notes']

def normalize_mac(value):
    s=re.sub(r'[^0-9A-Fa-f]','',value or '').upper()
    if not re.fullmatch(r'[0-9A-F]{12}',s):raise ValueError('MAC must be 12 hexadecimal digits')
    return s


def check_identity(mac,gpon):
    m=normalize_mac(mac)
    # Valid GPON SN on this platform is CMTD plus 8 hex characters = 12 chars.
    g=re.sub(r'[^0-9A-Za-z]','',gpon or '').upper()
    if not re.fullmatch(r'CMTD[0-9A-F]{8}',g):raise ValueError('GPON SN requires CMTD + 8 hexadecimal digits')
    if g != 'CMTD'+m[-8:]:raise ValueError('GPON SN differs from CMTD + MAC last 8; confirm label/device before writing')
    return m,g

@contextlib.contextmanager
def ledger_lock(folder):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    lock=folder/'.ip_ledger.lock'
    for attempt in range(60):
        try:
            fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
            os.write(fd,str(os.getpid()).encode());os.close(fd);break
        except FileExistsError:
            # Do not remove locks automatically: another operation may be in progress.
            time.sleep(.1)
    else:raise RuntimeError('IP ledger is locked; stop competing program and inspect lock before retry')
    try:yield
    finally:lock.unlink(missing_ok=True)

def read_ledger(folder):
    path=Path(folder)/'WAN_IP_Allocation.csv'
    if not path.exists():return []
    with path.open('r',encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def allocation_state(rows):
    # Latest status per MAC; historical entries remain for audit.
    current={}
    for row in rows:
        key=row.get('device_mac','')
        if key:current[key]=row
    return current

def reserve_ip(folder,mac,gpon,target_ip,router_ip,operator):
    if not ledger_initialized(folder):
        raise ValueError('Allocation ledger not initialized. Import old records or explicitly initialize a new ledger first.')
    mac,gpon=check_identity(mac,gpon)
    if ipaddress.IPv4Address(target_ip) not in ipaddress.IPv4Network('192.168.2.0/24') or not 121<=int(target_ip.split('.')[-1])<=130:
        raise ValueError('Allowed target IP range is 192.168.2.121 to 192.168.2.130')
    if not operator.strip():raise ValueError('Operator is required')
    with ledger_lock(folder):
        rows=read_ledger(folder); current=allocation_state(rows)
        for another,rec in current.items():
            if another!=mac and rec['target_ip']==target_ip and rec['result'] in ('RESERVED','OK','VERIFY_INCOMPLETE','MANUAL_OK','HOLD'):
                raise ValueError('IP '+target_ip+' is already assigned to MAC '+another)
            if another!=mac and rec['gpon_sn']==gpon and rec['result'] in ('RESERVED','OK','VERIFY_INCOMPLETE','MANUAL_OK','HOLD'):
                raise ValueError('GPON SN is already assigned to another MAC')
        prior=current.get(mac)
        if prior and prior['result'] in ('RESERVED','OK','VERIFY_INCOMPLETE','MANUAL_OK','HOLD') and prior['target_ip']!=target_ip:
            raise ValueError('This MAC already has target IP '+prior['target_ip']+'; manual review required')
        ledger_event(folder,'RESERVE','RESERVED',operator,mac,gpon,target_ip,router_ip,'reserved before write',locked=True)

def ledger_event(folder,event,result,operator,mac,gpon,target_ip,router_ip,notes='',locked=False):
    if not locked:
        with ledger_lock(folder):return ledger_event(folder,event,result,operator,mac,gpon,target_ip,router_ip,notes,True)
    path=Path(folder)/'WAN_IP_Allocation.csv'; path.parent.mkdir(parents=True,exist_ok=True)
    row=dict(time=datetime.now().isoformat(timespec='seconds'),event=event,result=result,
        operator=operator,device_mac=mac,gpon_sn=gpon,target_ip=target_ip,router_ip=router_ip,notes=notes)
    with path.open('a',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=LEDGER_FIELDS)
        if f.tell()==0:writer.writeheader()
        writer.writerow(row);f.flush();os.fsync(f.fileno())
    try:
        export_ledger_excel(folder)
    except (OSError,PermissionError):
        # CSV is committed; Excel file open in another process cannot revoke allocation.
        pass
    return row

def export_ledger_excel(folder):
    # Deliberately regenerate derived XLSX from append-only CSV so Excel is never
    # used as the transaction authority. Existing factory records stay preserved.
    from openpyxl import Workbook
    from openpyxl.styles import PatternFill, Font, Alignment
    from openpyxl.utils import get_column_letter
    wb=Workbook();ws=wb.active;ws.title='IP Allocation Record'
    extra='Port Mapping Transfer'
    ws.append(LEDGER_FIELDS+[extra])
    for r in read_ledger(folder):
        notes=r.get('notes','')
        transfer=TRANSFER_LABEL if ('Allowed Port Mapping Transfer: ' + TRANSFER_LABEL) in notes else ''
        ws.append([r.get(f,'') for f in LEDGER_FIELDS]+[transfer])
    ws.freeze_panes='A2';ws.auto_filter.ref=f'A1:J{ws.max_row}'
    widths=[22,17,22,18,20,20,20,20,74,32]
    for i,w in enumerate(widths,1):ws.column_dimensions[get_column_letter(i)].width=w
    for c in ws[1]:c.fill=PatternFill('solid',fgColor='17365D');c.font=Font(color='FFFFFF',bold=True);c.alignment=Alignment(vertical='center')
    ws.row_dimensions[1].height=25
    wb.save(Path(folder)/'WAN_IP_Allocation.xlsx')
