import tkinter as tk
from tkinter import ttk,messagebox
from pathlib import Path
from threading import Thread
from wan_tool import WanSession,TARGET

root=tk.Tk();root.title('GRG-4361u WAN Setting Tool V1.0.2 - Pilot');root.geometry('900x630')
frm=ttk.Frame(root,padding=14);frm.pack(fill='both',expand=True)
for i,(name,default,show) in enumerate([('DUT IP','192.168.1.1',None),('Username','admin',None),('Password','', '*')]):
    ttk.Label(frm,text=name).grid(row=i,column=0,sticky='w',pady=3)
    ent=ttk.Entry(frm,width=34,show=show);ent.insert(0,default);ent.grid(row=i,column=1,sticky='w')
    globals()['entry'+str(i)]=ent
info=ttk.Label(frm,text='Target: nas0_0 / VLAN160 / IPoE / INTERNET / Bridge / Fixed IP 192.168.2.121 / 10GE',wraplength=800)
info.grid(row=3,column=0,columnspan=3,sticky='w',pady=12)
text=tk.Text(frm,width=115,height=23);text.grid(row=6,column=0,columnspan=4,sticky='nsew',pady=10)
frm.rowconfigure(6,weight=1);frm.columnconfigure(2,weight=1)
state={'session':None,'busy':False}

def log(s):root.after(0,lambda:text.insert('end',s+'\n'));root.after(0,lambda:text.see('end'))
def busy(v):state['busy']=v;root.after(0,lambda:[b.configure(state='disabled' if v else 'normal') for b in (readbtn,applybtn)])
def run(fn):
    if state['busy']:return
    busy(True)
    def task():
        try: fn()
        except Exception as ex:log('ERROR: '+str(ex))
        finally:busy(False)
    Thread(target=task,daemon=True).start()
def read():
    if state['session'] is not None:
        state['session'].close()
    s=WanSession(entry0.get(),entry1.get(),entry2.get());state['session']=s
    result=s.read();log('READ OK: nas0_0')
    for k,v in result.items():log(f"{k:18s} current={str(v['current']):14s} target={v['target']}  {v['status']}")
    log('UNKNOWN fields require a proven device readback method before PASS.')
def apply():
    if not state['session'] or not state['session'].before_wan:
        messagebox.showwarning('Read first','Please use Read & Compare first.');return
    if not messagebox.askyesno('Experimental write','EXPERIMENTAL DUT WRITE. This can interrupt WAN connectivity and may alter TR069 provisioning. Proceed on a test DUT only?'):return
    win=tk.Toplevel(root);win.title('Confirm write');win.geometry('465x190');win.transient(root);win.grab_set()
    ttk.Label(win,text='Type exactly: APPLY nas0_0',padding=14).pack()
    e=ttk.Entry(win,width=30);e.pack();e.focus_set()
    def confirm():
        x=e.get();win.destroy()
        if x!='APPLY nas0_0':return
        def task():
            result,detail,basic=state['session'].apply_experimental(x)
            log('APPLY RESULT: '+result+' — '+detail)
            for k,v in basic.items():log(f"{k}: {v['status']}")
        run(task)
    ttk.Button(win,text='Confirm experimental write',command=confirm).pack(pady=12)
readbtn=ttk.Button(frm,text='1. Read & Compare',command=lambda:run(read));readbtn.grid(row=4,column=0,pady=4,sticky='w')
applybtn=ttk.Button(frm,text='2. EXPERIMENTAL Apply & Verify',command=apply);applybtn.grid(row=4,column=1,pady=4,sticky='w')
ttk.Label(frm,text='WARNING: No verified rollback. Do NOT use on production devices. Records written to ./records.',foreground='#a55b00',wraplength=800).grid(row=5,column=0,columnspan=3,sticky='w')
def shutdown():
    if state['session']:state['session'].close()
    root.destroy()
root.protocol('WM_DELETE_WINDOW',shutdown)
root.mainloop()
