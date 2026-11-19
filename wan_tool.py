from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
from html import escape
from bs4 import BeautifulSoup
import csv, json, ipaddress, re, time
from router_oqc.client import RouterClient, RouterError
from router_oqc.wan_config_client import read_wan, BRIDGE_FIELDS
from router_oqc.post_security import post_security_flag

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
    return {'interface':conf.name, 'vlan':conf.vlan, 'vid':conf.vid,
        'vprio':conf.vprio,'cmode':conf.cmode, 'brmode':conf.brmode,
        'napt':conf.napt, 'enable':conf.enable,'ctype':conf.applicationtype,
        'mtu':conf.mtu}


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
    """Conservative observation. Unknown fields MUST NOT be marked MATCH.

    WAN UI initializes form controls in JavaScript, so the static HTML alone
    cannot establish the selected link's actual IP or port map values.
    """
    out = {k: {'current': v['current'], 'target': v['target'],
               'status': 'MATCH' if v['match'] else 'DIFF'}
           for k,v in basic.items()}
    # 'br' enabled is distinct from brmode. Legacy JS parser cannot prove it.
    for key in ('br','multicast_vid','ipMode','ip','remoteIp','netmask','dnsMode','v6TunnelType','port10ge'):
        out[key] = {'current': None, 'target': target[key], 'status': 'UNKNOWN'}
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
    def __init__(self,host,username,password,output_dir='records'):
        self.host=host.strip();self.client=RouterClient(self.host,protocol='http',timeout=12)
        self.username=username;self.password=password;self.output_dir=Path(output_dir)
        self.before=None;self.token=None;self.html=None;self.before_wan=None

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
        self.comparison=extended_comparison(html,TARGET,compare_basic(wan,TARGET))
        read_result, counts = comparison_summary(self.comparison)
        write_record(self.output_dir,self.host,'READ',read_result,
                     'Read/Compare: '+str(counts),self.snapshot_before)
        (self.output_dir/'read_comparison.json').write_text(json.dumps(self.comparison,indent=2,ensure_ascii=False),encoding='utf-8')
        return self.comparison

    def apply_experimental(self,confirmation):
        if confirmation!='APPLY nas0_0':raise ValueError('Explicit confirmation required')
        if not self.before_wan or not self.html:raise ValueError('Read WAN first')
        # re-read before modification and prohibit changes since initial snapshot
        configs,token,html=read_wan(self.client)
        if {c.name:config_values(c) for c in configs}!=self.snapshot_before:
            raise ValueError('WAN settings changed since snapshot. Read again.')
        fields=build_payload(TARGET,token,html)  # fails closed until checksum is verified
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
            unchanged=all(after.get(name)==snapshot for name,snapshot in self.snapshot_before.items() if name!='nas0_0')
            basic=extended_comparison(new_html,TARGET,compare_basic(ensure_target_device(new_configs),TARGET))
            basic_ok=all(v['status']=='MATCH' for v in basic.values() if v['status']!='UNKNOWN')
            missing='Multicast VLAN / Static IP / bridge-checkbox / port mapping readback not proven from existing parser'
            # Never report PASS until all target settings can be verified.
            result='VERIFY_INCOMPLETE' if basic_ok and unchanged else 'FAIL'
            if not unchanged: missing='Non-target WAN settings changed'
            if not basic_ok: missing='Basic WAN setting mismatch'
            write_record(self.output_dir,self.host,'APPLY',result,missing,self.snapshot_before,after)
            (self.output_dir/'after.json').write_text(json.dumps(after,indent=2),encoding='utf-8')
            (self.output_dir/'after_comparison.json').write_text(json.dumps(basic,indent=2,ensure_ascii=False),encoding='utf-8')
            return result,missing,basic
        except Exception as exc:
            write_record(self.output_dir,self.host,'APPLY','FAIL',f'{type(exc).__name__}: {exc}',self.snapshot_before)
            raise


def save_manual_review(folder, host, comparison, confirmed, operator, notes):
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
    write_record(folder,host,'MANUAL_REVIEW',outcome,
                 'Operator='+operator.strip()+'; Auto='+automatic+'; '+notes.strip())
    return record
