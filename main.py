import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from threading import Thread
from wan_tool import WanSession, comparison_summary, save_manual_review, check_identity, read_ledger, allocation_state, ledger_event

VERSION = 'V1.0.6'
root=tk.Tk();root.title('GRG-4361u WAN Setting Tool V1.0.6 - Pilot');root.geometry('1160x830')
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
ttk.Label(frm,text='Operator').grid(row=6,column=0,sticky='w')
operator_ent=ttk.Entry(frm,width=36);operator_ent.grid(row=6,column=1,sticky='w')
ttk.Label(frm,text='Target: nas0_0 / VLAN160 / Multicast160 / IPoE / INTERNET / Bridge / Static IP / 10GE',wraplength=970).grid(row=7,column=0,columnspan=4,sticky='w',pady=8)
result_var=tk.StringVar(value='NOT TESTED')
counts_var=tk.StringVar(value='MATCH: —     DIFF: —     UNKNOWN: —')
result_label=tk.Label(frm,textvariable=result_var,font=('Segoe UI',18,'bold'),width=27,anchor='w')
result_label.grid(row=8,column=0,columnspan=2,sticky='w',pady=6)
ttk.Label(frm,textvariable=counts_var,font=('Segoe UI',10)).grid(row=8,column=2,columnspan=2,sticky='w')
state={'session':None,'busy':False,'comparison':None,'last_apply':False}

def refresh_allocation():
    rows=allocation_state(read_ledger('records'))
    used={v['target_ip'] for v in rows.values() if v['result'] in ('RESERVED','HOLD','OK','VERIFY_INCOMPLETE','MANUAL_OK')}
    allocation_var.set('Allocated / reserved: '+(', '.join(sorted(used,key=lambda a:int(a.split('.')[-1]))) if used else 'None'))
    return used

def show_result(value, comparison=None):
    if comparison is not None:
        _,c=comparison_summary(comparison)
        counts_var.set('MATCH: {MATCH}     DIFF: {DIFF}     UNKNOWN: {UNKNOWN}'.format(**c))
    result_var.set('OVERALL: '+value)
    palette={'OK':'#167a37','NG':'#b42318','FAIL':'#b42318','VERIFY_INCOMPLETE':'#a46100',
             'MANUAL_OK':'#167a37','MANUAL_NG':'#b42318','READ_ERROR':'#b42318'}
    result_label.configure(fg=palette.get(value,'#444444'))

def log(message):
    root.after(0,lambda:(text.insert('end',message+'\n'),text.see('end')))

def busy(v):
    state['busy']=v
    root.after(0,lambda:[b.configure(state='disabled' if v else 'normal') for b in (readbtn,applybtn,manualbtn)])

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
    session=WanSession(entries[0].get(),entries[1].get(),entries[2].get(),target_ip=ip_var.get(),mac=mac,gpon_sn=gpon,operator=operator_ent.get())
    state['session']=session
    comparison=session.read();state['comparison']=comparison;state['last_apply']=False
    overall,_=comparison_summary(comparison)
    root.after(0,lambda:show_result(overall,comparison))
    log('READ & COMPARE: '+overall)
    for k,v in comparison.items():
        log(f"{k:18s} current={str(v['current']):17s} target={v['target']}  {v['status']}")

def do_apply():
    if not state['session'] or not state['session'].before_wan:
        messagebox.showwarning('Read first','Use Read & Compare first.');return
    if (state['session'].target['ip']!=ip_var.get() or
        (state['session'].mac,state['session'].gpon_sn)!=check_identity(mac_ent.get(),gpon_ent.get())):
        messagebox.showwarning('Read again','Device identity or target IP changed. Read & Compare again first.');return
    if not messagebox.askyesno('Experimental DUT write','Write nas0_0 / target '+ip_var.get()+' / MAC '+state['session'].mac+'? TEST DUT ONLY. Continue?'):
        return
    confirm=simpledialog.askstring('Confirm write','Type exactly: APPLY nas0_0',parent=root)
    if confirm!='APPLY nas0_0':return
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
                mac_ent.delete(0,'end');gpon_ent.delete(0,'end')
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
                           state['comparison'],ans,operator,notes)
    log('HUMAN REVIEW: '+rec['manual_result']+' (auto result remains '+rec['automatic_result']+')')
    messagebox.showinfo('Manual review recorded',rec['manual_result']+' recorded separately. Auto result unchanged.')

readbtn=ttk.Button(frm,text='1. Read & Compare',command=lambda:run(do_read))
readbtn.grid(row=9,column=0,pady=8,sticky='w')
applybtn=ttk.Button(frm,text='2. EXPERIMENTAL Apply & Verify',command=do_apply)
applybtn.grid(row=9,column=1,pady=8,sticky='w')
manualbtn=ttk.Button(frm,text='3. Manual Web GUI Review',command=manual_review)
manualbtn.grid(row=9,column=2,pady=8,sticky='w')
ttk.Label(frm,text='Automatic UNKNOWN ≠ NG or PASS. Manual OK is recorded separately. No verified rollback; test DUT only.',foreground='#a46100',wraplength=970).grid(row=10,column=0,columnspan=4,sticky='w')
text=tk.Text(frm,width=135,height=26,font=('Consolas',10));text.grid(row=11,column=0,columnspan=4,sticky='nsew',pady=10)
frm.rowconfigure(11,weight=1);frm.columnconfigure(2,weight=1)

def shutdown():
    if state['busy']:
        messagebox.showwarning('Busy','Operation in progress. Do not close during WAN write.');return
    if state['session']:state['session'].close()
    root.destroy()
refresh_allocation()
root.protocol('WM_DELETE_WINDOW',shutdown)
root.mainloop()
