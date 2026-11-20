import tkinter as tk
from pathlib import Path
import sys
from tkinter import ttk, messagebox, simpledialog, filedialog
from threading import Thread
from wan_tool import WanSession, comparison_summary, save_manual_review, check_identity
from default_verify import snapshot, save_baseline, verify, baseline_path
from unified_store import ensure_workbook, read_rows, ip_state, import_legacy_csv, workbook_path, ACTIVE

VERSION = 'V1.1.2'
DATA_DIR = (Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent) / 'records'
ensure_workbook(DATA_DIR)
root=tk.Tk();root.title('GRG-4361u WAN Setting Tool V1.1.2');root.geometry('1160x830')
frm=ttk.Frame(root,padding=14);frm.pack(fill='both',expand=True)
entries=[]
for i,(name,default,show) in enumerate([('DUT IP','192.168.1.1',None),('Username','root',None),('Password','', '*')]):
    ttk.Label(frm,text=name).grid(row=i,column=0,sticky='w',pady=3)
    ent=ttk.Entry(frm,width=36,show=show);ent.insert(0,default);ent.grid(row=i,column=1,sticky='w')
    entries.append(ent)
ttk.Label(frm,text='Target Static IP').grid(row=3,column=0,sticky='w')
ip_choices=[f'192.168.2.{i}' for i in range(121,131)]
ip_var=tk.StringVar(value=ip_choices[0]);ip_box=ttk.Combobox(frm,textvariable=ip_var,values=ip_choices,state='readonly',width=19)
ip_box.grid(row=3,column=1,sticky='w',pady=5)
allocation_var=tk.StringVar(value='Used IPs: checking...')
ttk.Label(frm,textvariable=allocation_var,wraplength=520).grid(row=3,column=2,columnspan=2,sticky='w')
ttk.Label(frm,text='MAC (scan / input)').grid(row=4,column=0,sticky='w')
mac_ent=ttk.Entry(frm,width=36);mac_ent.grid(row=4,column=1,sticky='w')
ttk.Label(frm,text='GPON SN (CMTD + MAC last 8)').grid(row=5,column=0,sticky='w')
gpon_ent=ttk.Entry(frm,width=36);gpon_ent.grid(row=5,column=1,sticky='w')
# Operator is intentionally outside the scanner's Tab/Return sequence.
# It is configured once for a shift, and locked during DUT scanning.
operator_var=tk.StringVar(value='')
ttk.Label(frm,text='Operation Settings / Operator').grid(row=0,column=2,sticky='e',padx=8)
operator_ent=ttk.Entry(frm,width=20,textvariable=operator_var,state='readonly',takefocus=0)
operator_ent.grid(row=0,column=3,sticky='w')
def change_operator():
    if state['busy']:
        return
    value=simpledialog.askstring('Operator settings','Operator / Employee ID:',initialvalue=operator_var.get(),parent=root)
    if value is not None and value.strip():
        operator_var.set(value.strip())
        mac_ent.focus_set()
operator_btn=ttk.Button(frm,text='Change Operator',command=change_operator,takefocus=0)
operator_btn.grid(row=1,column=3,sticky='w')
# MAC scanner Enter -> GPON scanner; GPON scanner Enter stays on that field.
def mac_scan_complete(event=None):
    gpon_ent.focus_set()
    return 'break'
def gpon_scan_complete(event=None):
    # Do not let the scanner's Enter submit Apply or reach other controls.
    gpon_ent.focus_set()
    return 'break'
mac_ent.bind('<Return>',mac_scan_complete)
gpon_ent.bind('<Return>',gpon_scan_complete)
mac_ent.bind('<KP_Enter>',mac_scan_complete)
gpon_ent.bind('<KP_Enter>',gpon_scan_complete)
ttk.Label(frm,text='Target: nas0_0 / VLAN160 / Multicast160 / IPoE / INTERNET / Bridge / Static IP / 10GE',wraplength=970).grid(row=7,column=0,columnspan=4,sticky='w',pady=8)
result_var=tk.StringVar(value='NOT TESTED')
counts_var=tk.StringVar(value='MATCH: —     DIFF: —     UNKNOWN: —')
result_label=tk.Label(frm,textvariable=result_var,font=('Segoe UI',18,'bold'),width=27,anchor='w')
result_label.grid(row=8,column=0,columnspan=2,sticky='w',pady=6)
ttk.Label(frm,textvariable=counts_var,font=('Segoe UI',10)).grid(row=8,column=2,columnspan=2,sticky='w')
state={'session':None,'busy':False,'comparison':None,'last_apply':False}
mode_var=tk.StringVar(value='Engineering')
ttk.Label(frm,text='Mode').grid(row=7,column=2,sticky='e')
ttk.Combobox(frm,textvariable=mode_var,values=['Engineering','Production'],state='readonly',width=15).grid(row=7,column=3,sticky='w')

def refresh_allocation():
    rows=ip_state(DATA_DIR)
    used={v['Target IP'] for v in rows.values() if v['Result'] in ACTIVE}
    allocation_var.set('Allocated / reserved: '+(', '.join(sorted(used,key=lambda a:int(a.split('.')[-1]))) if used else 'None — Excel ready'))
    return used

def show_result(value, comparison=None):
    if comparison is not None:
        _,c=comparison_summary(comparison)
        counts_var.set('MATCH: {MATCH}     DIFF: {DIFF}     UNKNOWN: {UNKNOWN}'.format(**c))
    result_var.set('OVERALL: '+value)
    palette={'OK':'#167a37','NG':'#b42318','FAIL':'#b42318','VERIFY_INCOMPLETE':'#a46100',
             'MANUAL_OK':'#167a37','MANUAL_NG':'#b42318','READ_ERROR':'#b42318','READY_TO_APPLY':'#205b96','ALREADY_CONFIGURED':'#167a37'}
    result_label.configure(fg=palette.get(value,'#444444'))

def log(message):
    root.after(0,lambda:(text.insert('end',message+'\n'),text.see('end')))

def busy(v):
    state['busy']=v
    root.after(0,lambda:[b.configure(state='disabled' if v else 'normal') for b in (readbtn,applybtn,manualbtn,defaultbtn,capturebtn)])

def run(fn):
    if state['busy']:return
    busy(True)
    def task():
        try:fn()
        except Exception as e:
            log('ERROR: '+str(e));root.after(0,lambda:show_result('READ_ERROR' if not state['last_apply'] else 'FAIL'))
        finally:busy(False)
    Thread(target=task,daemon=True).start()

def do_read():
    if state['session']:state['session'].close()
    mac,gpon=check_identity(mac_ent.get(),gpon_ent.get())
    if not operator_ent.get().strip():raise ValueError('Operator required')
    session=WanSession(entries[0].get(),entries[1].get(),entries[2].get(),output_dir=DATA_DIR,target_ip=ip_var.get(),mac=mac,gpon_sn=gpon,operator=operator_ent.get(),mode=mode_var.get())
    state['session']=session
    comparison=session.read();state['comparison']=comparison;state['last_apply']=False
    overall,_=comparison_summary(comparison)
    read_display=('READY_TO_APPLY' if overall=='NG' else 'ALREADY_CONFIGURED' if overall=='OK' else overall)
    root.after(0,lambda:show_result(read_display,comparison))
    log('READ & COMPARE: '+read_display+' (configuration comparison: '+overall+')')
    for k,v in comparison.items():
        log(f"{k:18s} current={str(v['current']):17s} target={v['target']}  {v['status']}")

def do_apply():
    if not state['session'] or not state['session'].before_wan:
        messagebox.showwarning('Read first','Use Read & Compare first.');return
    if state['session'].mode != mode_var.get():
        messagebox.showwarning('Read again','Mode changed. Run Read & Compare again first.');return
    if (state['session'].target['ip']!=ip_var.get() or
        (state['session'].mac,state['session'].gpon_sn)!=check_identity(mac_ent.get(),gpon_ent.get())):
        messagebox.showwarning('Read again','Device identity or target IP changed. Read & Compare again first.');return
    if mode_var.get()=='Production' and not read_rows(DATA_DIR,1):
        if not messagebox.askyesno('Production allocation check','The Excel allocation list is EMPTY.\nConfirm existing DUT assignments have been audited (or import legacy CSV first).\nProceed with a new production allocation?'):
            return
    if not messagebox.askyesno('Confirm WAN write','TEST DUT ONLY — no verified rollback.\n\nWAN: nas0_0\nTarget IP: '+ip_var.get()+'\nMAC: '+state['session'].mac+'\nGPON SN: '+state['session'].gpon_sn+'\n\nApply & verify?'):
        return
    confirm='APPLY nas0_0'  # Internal API guard, not an operator typing step.
    def task():
        state['last_apply']=True
        result, detail, comparison=state['session'].apply_experimental(confirm)
        state['comparison']=comparison
        overall='OK' if result=='OK' else ('NG' if result=='FAIL' else 'VERIFY_INCOMPLETE')
        root.after(0,lambda:show_result(overall,comparison))
        log('APPLY RESULT: '+result+' — '+detail)
        for k,v in comparison.items():log(f"{k}: {v['status']}")
        root.after(0,refresh_allocation)
        if result=='OK':
            def advance():
                used=refresh_allocation()
                available=[ip for ip in ip_choices if ip not in used]
                if available:ip_var.set(available[0])
                mac_ent.delete(0,'end');gpon_ent.delete(0,'end');mac_ent.focus_set()
                log('Next DUT: scan new MAC + GPON SN, then Read & Compare.')
            root.after(0,advance)
        if result=='VERIFY_INCOMPLETE':
            root.after(0,lambda:messagebox.showwarning('Verification incomplete',
                'WAN write returned success, but automatic verification is incomplete.\n'
                'Check the WAN Web GUI fields and use Manual Web GUI Review to record the result.'))
    run(task)

def manual_review():
    if not state['comparison'] or not state['session']:
        messagebox.showwarning('Read first','Read or Apply first.');return
    operator=simpledialog.askstring('Reviewer','Operator / Engineer name:',parent=root)
    if not operator:return
    ans=messagebox.askyesnocancel('Manual Web GUI verification',
        'After refreshing nas0_0 in Web GUI, did ALL target fields match?\n'
        'YES = Manual OK; NO = Manual NG; Cancel = no record.\n'
        'This does NOT change any automatic UNKNOWN fields.')
    if ans is None:return
    notes=simpledialog.askstring('Manual review notes',
        'Notes / exceptions / screenshot reference (optional):',parent=root) or ''
    rec=save_manual_review(state['session'].output_dir,state['session'].host,
                           state['comparison'],ans,operator,notes,state['session'].mac,state['session'].gpon_sn,state['session'].target['ip'],state['session'].mode)
    log('HUMAN REVIEW: '+rec['manual_result']+' (auto result remains '+rec['automatic_result']+')')
    messagebox.showinfo('Manual review recorded',rec['manual_result']+' recorded separately. Auto result unchanged.')

readbtn=ttk.Button(frm,text='1. Read & Compare',command=lambda:run(do_read))
readbtn.grid(row=9,column=0,pady=8,sticky='w')
applybtn=ttk.Button(frm,text='2. EXPERIMENTAL Apply & Verify',command=do_apply)
applybtn.grid(row=9,column=1,pady=8,sticky='w')
manualbtn=ttk.Button(frm,text='3. Manual Web GUI Review',command=manual_review)
manualbtn.grid(row=9,column=2,pady=8,sticky='w')
ttk.Label(frm,text='Automatic UNKNOWN ≠ NG or PASS. Manual OK is recorded separately. No verified rollback; test DUT only.',foreground='#a46100',wraplength=970).grid(row=10,column=0,columnspan=4,sticky='w')
def import_old_records():
    if state['busy']:return
    path=filedialog.askopenfilename(title='Import legacy WAN_IP_Allocation.csv once',filetypes=[('Legacy CSV','*.csv')])
    if not path:return
    try:
        count=import_legacy_csv(DATA_DIR,path,mode_var.get())
        refresh_allocation()
        messagebox.showinfo('Imported',f'{count} legacy allocation events imported into Excel.\n'+str(workbook_path(DATA_DIR)))
    except Exception as exc:messagebox.showerror('Import blocked',str(exc))

def capture_golden():
    if state['busy']:return
    if baseline_path(DATA_DIR).exists():
        messagebox.showerror('Golden exists','Factory Golden already captured. Overwrite is blocked to protect the approved baseline.');return
    if not operator_var.get().strip():
        messagebox.showerror('Operator required','Set Operator before capturing Golden.');return
    if not messagebox.askyesno('Approve factory default Golden',
        'ONLY USE A VERIFIED FACTORY-RESTORED REFERENCE DUT.\n\n'
        'Confirm manually: this DUT has undergone Restore Default, rebooted and its factory default status was independently checked.\n\n'
        'Capture nas0_0/nas0_1/nas0_2 as a locked Golden baseline?'):
        return
    def task():
        data=snapshot(entries[0].get(),entries[1].get(),entries[2].get())
        item=save_baseline(DATA_DIR,data,operator_var.get(),True)
        log('Factory Golden saved, SHA256: '+item['sha256'])
        root.after(0,lambda:messagebox.showinfo('Golden captured','Golden captured. Review baseline JSON before enabling production verification.'))
    run(task)

def check_defaults():
    if state['busy']:return
    try:mac,gpon=check_identity(mac_ent.get(),gpon_ent.get())
    except Exception as exc:messagebox.showerror('Identity required',str(exc));return
    if not operator_var.get().strip():messagebox.showerror('Operator required','Set Operator first.');return
    if not messagebox.askyesno('Verify default (read only)',
        'Confirm DUT Restore Default and reboot are complete.\nNo settings will be written.\nRead WAN and compare approved Golden?'):
        return
    def task():
        result,counts,rows=verify(DATA_DIR,entries[0].get(),entries[1].get(),entries[2].get(),mac,gpon,operator_var.get(),mode_var.get())
        log('DEFAULT VERIFY: '+result+' '+str(counts))
        for interface,field,expected,actual,status in rows:
            if status!='MATCH':log(f'  {interface}.{field}: expected={expected}, actual={actual} [{status}]')
        root.after(0,lambda:show_result('OK' if result=='PASS' else 'NG' if result=='FAIL' else 'VERIFY_INCOMPLETE'))
        root.after(0,lambda:messagebox.showinfo('Default verification',result+'\n'+str(counts)))
    run(task)

capturebtn=ttk.Button(frm,text='Capture Factory Golden (once)',command=capture_golden)
capturebtn.grid(row=14,column=0,columnspan=2,sticky='w',pady=4)
defaultbtn=ttk.Button(frm,text='4. Verify Default Settings',command=check_defaults)
defaultbtn.grid(row=14,column=2,columnspan=2,sticky='w',pady=4)
ttk.Label(frm,text='Engineering = repeated test DUT; Production = strict IP uniqueness. Previous releases are not auto-imported.',foreground='#a46100',wraplength=980).grid(row=10,column=0,columnspan=4,sticky='e')
ttk.Label(frm,text='Excel: '+str(workbook_path(DATA_DIR)),wraplength=980).grid(row=11,column=0,columnspan=4,sticky='w')
ttk.Button(frm,text='Import legacy CSV (optional, one time)',command=import_old_records).grid(row=12,column=0,columnspan=3,sticky='w',pady=3)

text=tk.Text(frm,width=135,height=26,font=('Consolas',10));text.grid(row=13,column=0,columnspan=4,sticky='nsew',pady=10)
frm.rowconfigure(13,weight=1);frm.columnconfigure(2,weight=1)

def shutdown():
    if state['busy']:
        messagebox.showwarning('Busy','Operation in progress. Do not close during WAN write.');return
    if state['session']:state['session'].close()
    root.destroy()
refresh_allocation()
mac_ent.focus_set()
root.protocol('WM_DELETE_WINDOW',shutdown)
root.mainloop()
