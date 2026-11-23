"""Read-only, explicitly operator-approved factory-default baseline and verification."""
from __future__ import annotations
import hashlib,json,shutil,sys
from pathlib import Path
from datetime import datetime
from router_oqc.client import RouterClient
from router_oqc.wan_config_client import read_wan
from wan_tool import config_values
from unified_store import add_default_verification

BASELINE='GRG4361_Factory_Default_Golden.json'
VERSION='V1.1.4'

def snapshot(host,username,password):
    client=RouterClient(host.strip(),protocol='http',timeout=12)
    try:
        client.login(username,password)
        configs,_,_=read_wan(client)
        data={x.name:config_values(x) for x in configs}
        required={'nas0_0','nas0_1','nas0_2'}
        if not required.issubset(data):raise ValueError('Missing WAN interfaces: '+', '.join(sorted(required-set(data))))
        return data
    finally:client.close()

def baseline_path(folder):return Path(folder)/BASELINE

def install_reference_if_missing(folder):
    """Copy supplied validated Golden once. Do not overwrite a site-approved Golden.

    The bundled source was captured from user's 2026-11-20 records(10).zip.
    It is a user-captured reference, not proof of independent factory approval.
    """
    dest=baseline_path(folder)
    if dest.exists():return dest
    base=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))
    reference=base/'factory_default_reference.json'
    if not reference.exists():return None
    item=json.loads(reference.read_text(encoding='utf-8'))
    if item.get('sha256')!=_hash(item.get('interfaces')):
        raise ValueError('Bundled factory reference checksum mismatch')
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(reference,dest)
    return dest

def _hash(data):return hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False).encode('utf-8')).hexdigest()

def save_baseline(folder,data,operator,confirmed):
    if not confirmed:raise ValueError('Factory-default state must be explicitly confirmed')
    if not operator.strip():raise ValueError('Operator required')
    if not {'nas0_0','nas0_1','nas0_2'}.issubset(data):raise ValueError('Required WAN interfaces missing')
    path=baseline_path(folder)
    if path.exists():raise FileExistsError('Golden already exists. Remove it only after controlled review; overwriting is blocked.')
    item={'baseline_type':'OPERATOR_CONFIRMED_RESTORE_DEFAULT','created_at':datetime.now().isoformat(timespec='seconds'),
          'operator':operator,'interfaces':data,'sha256':_hash(data)}
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(item,ensure_ascii=False,indent=2),encoding='utf-8')
    return item

def load_baseline(folder):
    path=baseline_path(folder)
    if not path.exists():raise FileNotFoundError('Factory Default Golden missing. First restore a verified DUT, then capture Golden.')
    item=json.loads(path.read_text(encoding='utf-8'))
    if item.get('baseline_type')!='OPERATOR_CONFIRMED_RESTORE_DEFAULT' or item.get('sha256')!=_hash(item.get('interfaces')):
        raise ValueError('Golden provenance or SHA256 check failed')
    return item

def compare_defaults(expected,actual):
    rows=[];counts={'MATCH':0,'DIFF':0,'UNKNOWN':0}
    for interface in sorted(set(expected)|set(actual)):
        e=expected.get(interface,{})
        a=actual.get(interface,{})
        for field in sorted(set(e)|set(a)):
            if interface not in expected or field not in e or interface not in actual or field not in a or a[field] is None:
                status='UNKNOWN'
            else:status='MATCH' if type(e[field]) is type(a[field]) and e[field]==a[field] else 'DIFF'
            rows.append((interface,field,e.get(field,'<MISSING>'),a.get(field,'<MISSING>'),status));counts[status]+=1
    result='FAIL' if counts['DIFF'] else 'VERIFY_INCOMPLETE' if counts['UNKNOWN'] or not rows else 'PASS'
    return result,counts,rows

def verify(folder,host,user,password,mac,gpon,operator,mode):
    install_reference_if_missing(folder)
    item=load_baseline(folder)
    current=snapshot(host,user,password)
    result,counts,rows=compare_defaults(item['interfaces'],current)
    from unified_store import last_wan_apply
    linked=last_wan_apply(folder,mac,gpon)
    relation=('Linked WAN APPLY '+linked['Time']+' / '+linked['Result']+' / '+linked['Target IP']) if linked else 'No prior WAN APPLY in this workbook; independent default verification'
    detail='Factory default: '+str(counts)+'; '+relation
    add_default_verification(folder,VERSION,mode,host,mac,gpon,operator,result,counts,item['sha256'],detail,rows)
    folder=Path(folder)
    (folder/'default_verification_latest.json').write_text(json.dumps({'result':result,'counts':counts,'golden_sha256':item['sha256'],'actual':current,'comparison':rows},ensure_ascii=False,indent=2),encoding='utf-8')
    with (folder/'execution.log').open('a',encoding='utf-8') as f:f.write(datetime.now().isoformat()+' DEFAULT_VERIFY '+result+' '+detail+'\n')
    return result,counts,rows
