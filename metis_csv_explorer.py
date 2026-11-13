#!/usr/bin/env python3
"""METIS CT CSV Explorer — tkinter GUI, Python standard library only.

Reads existing METIS exporter CSVs locally. Does not transmit data.
"""
from __future__ import annotations
import csv
import datetime as dt
import math
import os
import re
import statistics
import threading
import tkinter as tk
from collections import Counter
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED

APP = 'METIS CT Data Explorer'
MISSING = {'', 'n/a', 'na', 'null', 'none', 'nan', 'not available', 'unknown'}
KINDS = [
 ('CT_IQ_Dose_Size', 'Integrated series-level dataset'),
 ('CTIQ', 'Image quality'), ('CTSIZE', 'Patient size'),
 ('CTRDSREVENTS', 'RDSR irradiation events'),
 ('CTORGANDOSE', 'Organ dose'), ('CTSERIESTAGS', 'DICOM series metadata'),
]
DESCRIPTION = {
 'CT_IQ_Dose_Size': 'Joined series-level CT imaging, size, dose and image-quality data. Verify linkage and missing fields before statistical modeling.',
 'CTIQ': 'Image-quality results, including noise, NPS, MTF, contrast and WED profile.',
 'CTSIZE': 'Scout-derived effective size; validate units against source methodology.',
 'CTRDSREVENTS': 'Radiation Dose Structured Report parameters (one or more events per study).',
 'CTORGANDOSE': 'Per-organ estimated absorbed/equivalent dose; verify units and dose definitions with data provider.',
 'CTSERIESTAGS': 'DICOM parameters and metadata; can contain patient or institutional identifiers.',
}
LABELS = {
 'StudyInstanceUID':'Study UID', 'SeriesInstanceUID':'Series UID', 'IrradiationEventUID':'Irradiation event UID',
 'AccessionNumber':'Accession number', 'DICOM_StudyDate':'Study date', 'DICOM_StationName':'CT station',
 'DICOM_ManufacturerModelName':'Scanner model', 'DICOM_ProtocolName':'Protocol',
 'DICOM_BodyPartExamined':'Body part', 'DICOM_SeriesDescription':'Series description',
 'SERIES_NumberOfImages':'Number of images', 'DICOM_Patient_Age':'Patient age',
 'DICOM_Patient_Sex':'Patient sex', 'DICOM_Patient_Size':'Patient height (check units)',
 'DICOM_Patient_Weight':'Patient weight (check units)',
 'DICOM_SliceThickness':'Slice thickness (mm)', 'DICOM_KVP':'Tube voltage (kVp)',
 'DICOM_XRayTubeCurrent':'Tube current (mA)', 'DICOM_SpiralPitchFactor':'Spiral pitch',
 'IQ_AverageGlobalNoiseIndex':'Average noise index', 'IQ_NPSfav':'NPS average frequency',
 'IQ_NPSfpeak':'NPS peak frequency', 'IQ_NPSf10':'NPS f10',
 'IQ_MTFf10':'MTF f10', 'IQ_MTFf10_std':'MTF f10 SD',
 'IQ_AverageGlobalContrastIndex':'Contrast index', 'IQ_dPrime':'Detectability index (d′)',
 'SIZE_AverageWaterEquivalentDiameter_IMAGE':'Average WED (image; verify units)',
 'SIZE_EffectiveSize_SCOUT':'Effective size (scout; verify units)',
 'RDSR_CTDIvol':'CTDIvol (mGy; verify)', 'RDSR_DLP':'DLP (mGy·cm; verify)',
 'DICOM_CTDIvol':'DICOM CTDIvol (mGy; verify)', 'DICOM_DLP':'DICOM DLP (mGy·cm; verify)',
 'RDSR_kVp':'RDSR kVp', 'RDSR_mA':'RDSR mA', 'RDSR_Pitch':'RDSR pitch',
 'AverageWaterEquivalentDiameter':'Average WED (verify units)',
 'EffectiveSize':'Effective size (verify units)',
 'AverageGlobalNoiseIndex':'Average noise index', 'AverageGlobalContrastIndex':'Contrast index',
 'CT Dose_Mean CTDIvol':'RDSR CTDIvol (mGy; verify)', 'CT Dose_DLP':'RDSR DLP (mGy·cm; verify)',
 'Image_StudyInstanceUID':'Study UID', 'Image_SeriesInstanceUID':'Series UID',
 'Image_AccessionNumber':'Accession number', 'Image_StudyDate':'Study date',
 'Image_SeriesDescription':'Series description', 'Image_StationName':'CT station',
 'Patient_ID':'Patient ID (sensitive)', 'Patient_BirthDate':'Birth date (sensitive)',
 'Patient_PatientBirthDate':'Birth date (sensitive)',
 'Image_InstitutionName':'Institution (potentially sensitive)',
 'Image_OperatorsName':'Operator name (sensitive)',
}
SENSITIVE = re.compile(r'(patient.?id|birthdate|birth.?date|accession|patient.?name|operator.?name|physician|institutionname|series_path|device.?serial|studyinstanceuid|seriesinstanceuid|sopinstanceuid|irradiationeventuid|radiation_event_uid)', re.I)


def classify(name):
 upper = name.upper()
 for key, _ in KINDS:
  if upper.startswith(key.upper()+'_') or upper == key.upper()+'.CSV':
   return key
 if upper.startswith('CTORGANSOE_'):
  return 'CTORGANDOSE'
 return 'Other CSV'


def label(column):
 if column in LABELS:
  return LABELS[column]
 if column.startswith('ORGAN_DOSE_'):
  return 'Organ dose: '+column[len('ORGAN_DOSE_'):]
 if column.startswith(('Image_', 'DICOM_', 'IQ_', 'RDSR_', 'CT Acquisition Parameters_')):
  return re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', column).replace('_', ' ')
 return column.replace('_',' ')


def category(col):
 s = col.lower()
 if SENSITIVE.search(col): return 'Identifiers / privacy'
 if 'organ_dose_' in s or col in ['Marrow','Bones','Skin','Brain','Eyes','Thyroid','Lungs','Heart','Liver','Kidneys','Equivalent Dose']:
  return 'Organ dose'
 if s.startswith('iq_') or any(x in s for x in ('noise','nps','mtf','contrast','dprime','error')):
  return 'Image quality'
 if s.startswith('size_') or any(x in s for x in ('watersize','waterequivalent','effectivesize','patient_size','patient_weight','patient_age','patient_sex')):
  return 'Patient / size'
 if s.startswith('rdsr_') or any(x in s for x in ('ctdi','dlp','dose_', 'irradiation','ct acquisition parameters')):
  return 'Radiation dose / RDSR'
 if s.startswith('dicom_') or s.startswith('image_'):
  return 'DICOM / acquisition'
 return 'Other'


def blank(value):
 return str(value).strip().lower() in MISSING


def num(value):
 try:
  if blank(value): return None
  val = float(value)
  return val if math.isfinite(val) else None
 except (ValueError,TypeError): return None


def numeric_column(col):
 s=col.lower()
 if re.search(r'(uid|_id$|accession|date|time_date|time_time|station|serial|version|patient_id|sop|studytime|study_time)',s): return False
 return True


def safe_excel_text(s):
 s = str(s).replace('\x00','')[:32767]
 return "'"+s if s.lstrip().startswith(('=','+','-','@')) else s


def excel_col(n):
 out=''
 while n:
  n,r=divmod(n-1,26);out=chr(65+r)+out
 return out


def xcell(ref, value, style=0, numeric=False):
 if blank(value): return ''
 if numeric:
  v=num(value)
  if v is not None: return f'<c r="{ref}" s="{style}" t="n"><v>{v:.15g}</v></c>'
 txt = escape(safe_excel_text(value), {'"':'&quot;'})
 return f'<c r="{ref}" s="{style}" t="inlineStr"><is><t xml:space="preserve">{txt}</t></is></c>'


def sheet_xml(name, headers, rows, aliases=False):
 """Yield worksheet XML in chunks; no arbitrary code execution."""
 yield '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
 yield '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
 yield '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
 yield '<sheetFormatPr defaultRowHeight="16"/>'
 yield '<cols>'
 for i,h in enumerate(headers,1):
  width=min(45,max(15,len(str(h))+2))
  yield f'<col min="{i}" max="{i}" width="{width}" customWidth="1"/>'
 yield '</cols><sheetData>'
 yield '<row r="1">'+''.join(xcell(f'{excel_col(j)}1', h, 1) for j,h in enumerate(headers,1))+'</row>'
 for idx,row in enumerate(rows,2):
  if idx>1048576: raise ValueError(f'Excel row limit exceeded for {name}')
  parts=[]
  for j,(h,val) in enumerate(zip(headers,row),1):
   parts.append(xcell(f'{excel_col(j)}{idx}',val,2,numeric_column(h)))
  yield f'<row r="{idx}">'+''.join(parts)+'</row>'
 yield '</sheetData>'
 if headers:
  last=f'{excel_col(len(headers))}{max(1,len(rows)+1)}'
  yield f'<autoFilter ref="A1:{last}"/>'
 yield '</worksheet>'


def write_xlsx(path, sheets):
 """Create genuine, styled, filterable XLSX with stdlib zip/xml only."""
 if not sheets: raise ValueError('No datasets to export')
 sheets = [(name[:31],header,rows) for name,header,rows in sheets]
 names=[s[0] for s in sheets]
 if len(names)!=len(set(names)): raise ValueError('Duplicate sheet names')
 with ZipFile(path,'w',ZIP_DEFLATED,compresslevel=6) as z:
  z.writestr('[Content_Types].xml','<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'+''.join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(1,len(sheets)+1))+'</Types>')
  z.writestr('_rels/.rels','<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
  z.writestr('xl/workbook.xml','<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'+''.join(f'<sheet name="{escape(name,{chr(34):"&quot;"})}" sheetId="{i}" r:id="rId{i}"/>' for i,(name,_,_) in enumerate(sheets,1))+'</sheets></workbook>')
  z.writestr('xl/_rels/workbook.xml.rels','<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+''.join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1,len(sheets)+1))+'<Relationship Id="rId999" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
  z.writestr('xl/styles.xml','<?xml version="1.0" encoding="UTF-8"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="10"/><name val="Aptos"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="10"/><name val="Aptos"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF17456A"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')
  for i,(name,headers,rows) in enumerate(sheets,1):
   with z.open(f'xl/worksheets/sheet{i}.xml','w') as fh:
    for part in sheet_xml(name,headers,rows): fh.write(part.encode('utf-8'))


def read_csv(path):
 with open(path,encoding='utf-8-sig',newline='') as f:
  reader=csv.DictReader(f)
  if not reader.fieldnames: raise ValueError('Empty CSV')
  headers=list(reader.fieldnames)
  rows=[]
  for r in reader:
   rows.append({h: r.get(h,'') or '' for h in headers})
 return headers, rows


class Explorer(tk.Tk):
 def __init__(self):
  super().__init__()
  self.title(APP+'  |  Local, offline')
  self.geometry('1440x850');self.minsize(1050,630)
  self.datasets={};self.current=None;self.filtered=[];self.page=0;self.page_size=100
  self.query=tk.StringVar();self.group=tk.StringVar(value='All fields')
  self.display=tk.StringVar(value='Readable labels');self.status=tk.StringVar(value='Open a folder containing METIS CSV exports to begin.')
  self.hide_sensitive=tk.BooleanVar(value=False)
  self.sort_col=None;self.sort_reverse=False
  self.make_ui()
  self.query.trace_add('write',lambda *_:self.filter_rows())

 def make_ui(self):
  s=ttk.Style(self)
  try: s.theme_use('clam')
  except tk.TclError: pass
  s.configure('Treeview',rowheight=25);s.configure('Treeview.Heading',font=('DejaVu Sans',10,'bold'))
  top=ttk.Frame(self,padding=10);top.pack(fill='x')
  ttk.Label(top,text='METIS CT Data Explorer',font=('DejaVu Sans',18,'bold')).pack(side='left',padx=(0,20))
  ttk.Button(top,text='Open folder',command=self.open_folder).pack(side='left',padx=3)
  ttk.Button(top,text='Add CSV files',command=self.open_files).pack(side='left',padx=3)
  ttk.Button(top,text='Export current view',command=self.export_current).pack(side='right',padx=3)
  ttk.Button(top,text='Export all datasets',command=self.export_all).pack(side='right',padx=3)
  center=ttk.PanedWindow(self,orient='horizontal');center.pack(fill='both',expand=True,padx=8,pady=5)
  side=ttk.Frame(center,width=280);center.add(side,weight=0)
  ttk.Label(side,text='Loaded datasets',font=('DejaVu Sans',12,'bold')).pack(anchor='w',pady=4)
  self.source_list=tk.Listbox(side,exportselection=False,width=35,font=('DejaVu Sans',10))
  self.source_list.pack(fill='both',expand=True)
  self.source_list.bind('<<ListboxSelect>>',self.select_source)
  ttk.Label(side,text='Select one export per timestamp.\nFiles are not merged automatically.',foreground='#535f67',justify='left').pack(anchor='w',pady=8)
  right=ttk.Frame(center);center.add(right,weight=1)
  self.notebook=ttk.Notebook(right);self.notebook.pack(fill='both',expand=True)
  self.table_tab=ttk.Frame(self.notebook);self.profile_tab=ttk.Frame(self.notebook);self.dict_tab=ttk.Frame(self.notebook)
  self.notebook.add(self.table_tab,text='  Data table  ');self.notebook.add(self.profile_tab,text='  Data quality & statistics  ');self.notebook.add(self.dict_tab,text='  Data dictionary  ')
  filters=ttk.Frame(self.table_tab,padding=6);filters.pack(fill='x')
  ttk.Label(filters,text='Search rows:').pack(side='left')
  ttk.Entry(filters,textvariable=self.query,width=26).pack(side='left',padx=6)
  ttk.Label(filters,text='Field group:').pack(side='left',padx=(8,3))
  self.groups=ttk.Combobox(filters,textvariable=self.group,state='readonly',width=22)
  self.groups.pack(side='left');self.groups.bind('<<ComboboxSelected>>',lambda *_:self.render_table())
  self.groups['values']=['All fields']
  ttk.Combobox(filters,textvariable=self.display,values=['Readable labels','Original column names'],state='readonly',width=21).pack(side='left',padx=8)
  self.display.trace_add('write',lambda *_:self.render_table())
  ttk.Checkbutton(filters,text='Hide sensitive columns',variable=self.hide_sensitive,command=self.render_table).pack(side='left',padx=6)
  treeframe=ttk.Frame(self.table_tab);treeframe.pack(fill='both',expand=True)
  self.tree=ttk.Treeview(treeframe,show='headings',selectmode='browse')
  ys=ttk.Scrollbar(treeframe,orient='vertical',command=self.tree.yview)
  xs=ttk.Scrollbar(treeframe,orient='horizontal',command=self.tree.xview)
  self.tree.configure(yscrollcommand=ys.set,xscrollcommand=xs.set)
  self.tree.grid(row=0,column=0,sticky='nsew');ys.grid(row=0,column=1,sticky='ns');xs.grid(row=1,column=0,sticky='ew')
  treeframe.rowconfigure(0,weight=1);treeframe.columnconfigure(0,weight=1)
  self.tree.bind('<Double-1>',self.show_cell)
  footer=ttk.Frame(self.table_tab,padding=6);footer.pack(fill='x')
  ttk.Button(footer,text='◀ Previous',command=lambda:self.move_page(-1)).pack(side='left')
  ttk.Button(footer,text='Next ▶',command=lambda:self.move_page(1)).pack(side='left',padx=5)
  self.count=ttk.Label(footer,text='');self.count.pack(side='left',padx=12)
  ttk.Label(footer,text='Double-click a row for full values',foreground='#596771').pack(side='right')
  self.profile_tree=self.make_tree(self.profile_tab,['Field','Available','Missing %','Unique','Min','Median','Max'])
  self.dict_tree=self.make_tree(self.dict_tab,['Original column','Readable meaning','Group','Missing %','Sensitive?'])
  ttk.Label(self,textvariable=self.status,relief='sunken',anchor='w',padding=5).pack(fill='x',side='bottom')

 def make_tree(self,parent,headers):
  fr=ttk.Frame(parent);fr.pack(fill='both',expand=True)
  tv=ttk.Treeview(fr,columns=headers,show='headings')
  for x in headers:
   tv.heading(x,text=x);tv.column(x,width=165 if x not in ('Original column','Readable meaning') else 260,anchor='w')
  sy=ttk.Scrollbar(fr,orient='vertical',command=tv.yview);sx=ttk.Scrollbar(fr,orient='horizontal',command=tv.xview)
  tv.configure(yscrollcommand=sy.set,xscrollcommand=sx.set)
  tv.grid(row=0,column=0,sticky='nsew');sy.grid(row=0,column=1,sticky='ns');sx.grid(row=1,column=0,sticky='ew')
  fr.rowconfigure(0,weight=1);fr.columnconfigure(0,weight=1)
  return tv

 def open_folder(self):
  folder=filedialog.askdirectory(title='Select METIS exporter output folder')
  if folder:
   files=sorted(Path(folder).glob('*.csv'))
   if not files: messagebox.showinfo('No files','No CSV files found in that folder.');return
   self.add_files(files)
 def open_files(self):
  files=filedialog.askopenfilenames(title='Select METIS CSV files',filetypes=[('CSV files','*.csv'),('All files','*.*')])
  if files:self.add_files([Path(x) for x in files])
 def add_files(self,files):
  bad=[];added=0
  for path in files:
   key=str(Path(path).resolve())
   if key in self.datasets:continue
   try:
    heads,rows=read_csv(path)
    self.datasets[key]={'name':Path(path).name,'kind':classify(Path(path).name),'headers':heads,'rows':rows}
    added+=1
   except Exception as e:bad.append(f'{Path(path).name}: {e}')
  self.source_keys=sorted(self.datasets,key=lambda k:(self.datasets[k]['kind'],self.datasets[k]['name']))
  self.source_list.delete(0,'end')
  for k in self.source_keys:
   d=self.datasets[k];self.source_list.insert('end',f'{d["kind"]}  |  {d["name"][-19:-4]}  ({len(d["rows"]):,})')
  if self.source_keys:
   self.source_list.selection_clear(0,'end');self.source_list.selection_set(0);self.select_source()
  self.status.set(f'{added} new CSV file(s) loaded. {len(self.datasets)} total. No data leaves this computer.')
  if bad:messagebox.showwarning('Files not loaded','\n'.join(bad[:12]))
 def select_source(self,event=None):
  sel=self.source_list.curselection()
  if not sel:return
  self.current=self.source_keys[sel[0]];self.group.set('All fields');self.query.set('')
  cols=self.datasets[self.current]['headers']
  groups=sorted(set(category(x) for x in cols))
  self.groups['values']=['All fields']+groups
  self.filtered=list(range(len(self.datasets[self.current]['rows'])));self.page=0;self.sort_col=None
  self.render_table();self.render_profile()
 def filter_rows(self):
  if not self.current:return
  d=self.datasets[self.current];q=self.query.get().casefold().strip()
  self.filtered=[i for i,r in enumerate(d['rows']) if not q or any(q in str(v).casefold() for v in r.values())]
  self.page=0;self.render_table()
 def columns(self):
  if not self.current:return []
  heads=self.datasets[self.current]['headers'];group=self.group.get()
  return [h for h in heads if (group=='All fields' or category(h)==group) and (not self.hide_sensitive.get() or not SENSITIVE.search(h))]
 def render_table(self):
  if not self.current:return
  d=self.datasets[self.current];cols=self.columns()
  self.tree.delete(*self.tree.get_children());self.tree['columns']=cols
  for h in cols:
   shown=label(h) if self.display.get()=='Readable labels' else h
   self.tree.heading(h,text=shown,command=lambda c=h:self.sort(c))
   self.tree.column(h,width=min(310,max(120,len(shown)*8+18)),minwidth=80,stretch=False)
  start=self.page*self.page_size
  for ix in self.filtered[start:start+self.page_size]:
   r=d['rows'][ix]
   self.tree.insert('','end',iid=str(ix),values=[(str(r[h])[:130]+'…' if len(str(r[h]))>130 else r[h]) for h in cols])
  np=max(1,(len(self.filtered)+self.page_size-1)//self.page_size)
  self.count.config(text=f'{len(self.filtered):,} / {len(d["rows"]):,} rows  |  {len(cols)} columns  |  Page {self.page+1}/{np}')
 def move_page(self,step):
  n=max(1,(len(self.filtered)+self.page_size-1)//self.page_size)
  self.page=max(0,min(n-1,self.page+step));self.render_table()
 def sort(self,col):
  if not self.current:return
  if self.sort_col==col:self.sort_reverse=not self.sort_reverse
  else:self.sort_col=col;self.sort_reverse=False
  rows=self.datasets[self.current]['rows']
  def key(i):
   s=rows[i][col];n=num(s)
   return (blank(s),0,n) if n is not None and numeric_column(col) else (blank(s),1,str(s).casefold())
  self.filtered.sort(key=key,reverse=self.sort_reverse);self.page=0;self.render_table()
 def show_cell(self,event=None):
  if not self.current:return
  sel=self.tree.selection()
  if not sel:return
  r=self.datasets[self.current]['rows'][int(sel[0])]
  w=tk.Toplevel(self);w.title('Full record | '+self.datasets[self.current]['name']);w.geometry('900x620')
  box=tk.Text(w,wrap='word',font=('DejaVu Sans Mono',10));box.pack(fill='both',expand=True)
  for h in self.columns():box.insert('end',f'{label(h)}\n  {h}\n  {r.get(h, "")}\n\n')
  box.config(state='disabled')
 def render_profile(self):
  if not self.current:return
  d=self.datasets[self.current];rows=d['rows'];total=len(rows)
  self.profile_tree.delete(*self.profile_tree.get_children());self.dict_tree.delete(*self.dict_tree.get_children())
  for h in d['headers']:
   vals=[r.get(h,'') for r in rows];valid=[v for v in vals if not blank(v)]
   pct=(100*(total-len(valid))/total) if total else 0
   unique=len(set(valid))
   numeric=[num(v) for v in valid] if numeric_column(h) else []
   numeric=[v for v in numeric if v is not None]
   if valid and len(numeric)/len(valid)>=.85 and numeric:
    mn=f'{min(numeric):.5g}';med=f'{statistics.median(numeric):.5g}';mx=f'{max(numeric):.5g}'
   else:mn=med=mx='—'
   self.profile_tree.insert('','end',values=(label(h),len(valid),f'{pct:.1f}%',unique,mn,med,mx))
   self.dict_tree.insert('','end',values=(h,label(h),category(h),f'{pct:.1f}%', 'YES' if SENSITIVE.search(h) else 'No'))
 def export_current(self):
  if not self.current:messagebox.showinfo('Nothing loaded','Load a CSV first.');return
  d=self.datasets[self.current];cols=self.columns()
  if not cols:messagebox.showwarning('No fields','No columns selected.');return
  rows=[[d['rows'][i][h] for h in cols] for i in self.filtered]
  note=[['Dataset',d['name']],['Kind',d['kind']],['Rows',str(len(rows))],['Columns',str(len(cols))],['Filter',self.query.get() or '(none)'],['Field group',self.group.get()],['Exported (local)',dt.datetime.now().isoformat(timespec='seconds')],['Warning','Check patient identifiers and sharing approvals before distributing.'],['Dose and size units','Verify from exporter definitions before scientific interpretation.']]
  glossary=[[h,label(h),category(h),'YES' if SENSITIVE.search(h) else 'No'] for h in cols]
  self.save_excel([('README',['Item','Value'],note),('Current view',cols,rows),('Dictionary',['Field','Meaning','Group','Sensitive'],glossary)],'METIS_current_view.xlsx')
 def export_all(self):
  if not self.datasets:messagebox.showinfo('Nothing loaded','Load CSVs first.');return
  chosen={}
  # One dataset of each type; if multiple runs exist, pick the most recently named timestamp.
  for k in sorted(self.datasets,key=lambda x:self.datasets[x]['name']):
   d=self.datasets[k];chosen[d['kind']]=d
  if len(chosen)<len(self.datasets):
   if not messagebox.askyesno('Multiple export runs', 'Multiple timestamps were loaded. The workbook will include the latest filename for each dataset type. Continue?'):
    return
  readme=[['Description','METIS CT Data Exporter — Excel package'],['Exported (local)',dt.datetime.now().isoformat(timespec='seconds')],['Data sensitivity','Contains potentially identifiable DICOM/patient information. Review before sharing.'],['File selection','Latest filename per CSV type'],['Units','Not independently verified; check exporter/source specifications.']]
  sheets=[('README',['Item','Value'],readme)];dictionary=[]
  used=set()
  for kind,d in chosen.items():
   sheet=kind[:31]
   if sheet in used:sheet=f'Sheet{len(used)+1}'
   used.add(sheet)
   heads=d['headers'];sheets.append((sheet,heads,[[r[h] for h in heads] for r in d['rows']]))
   dictionary.extend([[kind,h,label(h),category(h),'YES' if SENSITIVE.search(h) else 'No'] for h in heads])
  sheets.append(('Dictionary',['Dataset','Original field','Description','Group','Sensitive'],dictionary))
  self.save_excel(sheets,'METIS_all_datasets.xlsx')
 def save_excel(self,sheets,default):
  file=filedialog.asksaveasfilename(title='Export Excel workbook',defaultextension='.xlsx',initialfile=default,filetypes=[('Excel workbook','*.xlsx')])
  if not file:return
  try:
   self.config(cursor='watch');self.update_idletasks()
   write_xlsx(file,sheets)
   self.status.set(f'Excel workbook saved: {file}')
   messagebox.showinfo('Export complete',f'Excel saved successfully:\n{file}\n\nReview privacy and units before sharing.')
  except Exception as e:
   messagebox.showerror('Excel export failed',str(e))
  finally:self.config(cursor='')

if __name__=='__main__':
 app=Explorer();app.mainloop()
