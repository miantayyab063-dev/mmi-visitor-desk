"""Portable Excel export for MMI. Uses only Python's standard library."""
import io,zipfile,re
from xml.sax.saxutils import escape
from datetime import datetime

def column(n):
    s=''
    while n:n,r=divmod(n-1,26);s=chr(65+r)+s
    return s

def clean(s):return escape(re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]','',str(s)))

def workbook(sheets):
    """Identifiers remain strings (leading zeroes preserved); no input becomes a formula."""
    out=io.BytesIO()
    ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml','<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'+''.join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(1,len(sheets)+1))+'</Types>')
        z.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr('xl/workbook.xml',f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'+''.join(f'<sheet name="{clean(name)}" sheetId="{i}" r:id="rId{i}"/>' for i,(name,_) in enumerate(sheets,1))+'</sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+''.join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1,len(sheets)+1))+f'<Relationship Id="rId{len(sheets)+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
        z.writestr('xl/styles.xml',f'<styleSheet xmlns="{ns}"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF10283F"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="3"><xf fontId="0" fillId="0" borderId="0" xfId="0"/><xf fontId="1" fillId="2" borderId="0" xfId="0" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf><xf fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')
        for i,(name,rows) in enumerate(sheets,1):
            widths=[max(16,min(45,max((len(str(r[j] or '')) for r in rows[:200] if j<len(r)),default=16))) for j in range(len(rows[0]))]
            xml=f'<worksheet xmlns="{ns}"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols>'+''.join(f'<col min="{j}" max="{j}" width="{w}" customWidth="1"/>' for j,w in enumerate(widths,1))+'</cols><sheetData>'
            for n,row in enumerate(rows,1):
                xml+=f'<row r="{n}" ht="{32 if n==1 else 42}" customHeight="1">'
                for j,value in enumerate(row,1):
                    style=1 if n==1 else 2;ref=f'{column(j)}{n}'
                    if isinstance(value,(int,float)):xml+=f'<c r="{ref}" s="{style}" t="n"><v>{value}</v></c>'
                    else:xml+=f'<c r="{ref}" s="{style}" t="inlineStr"><is><t xml:space="preserve">{clean(value if value is not None else "")}</t></is></c>'
                xml+='</row>'
            xml+='</sheetData>'+f'<autoFilter ref="A1:{column(len(rows[0]))}{len(rows)}"/></worksheet>'
            z.writestr(f'xl/worksheets/sheet{i}.xml',xml)
    return out.getvalue()

def export(c):
    # One read transaction: all sheets represent the same database snapshot.
    c.execute('BEGIN')
    people=[list(r) for r in c.execute('SELECT id,name,mobile,cnic FROM visitors ORDER BY id')]
    visits=[list(r) for r in c.execute('SELECT t.id,v.id,t.snapshot_name,t.snapshot_mobile,t.snapshot_cnic,t.at,t.out_at,t.host,t.purpose,t.staff,t.remarks,t.out_by,t.updated_at,t.updated_by,t.version FROM visits t JOIN visitors v ON v.id=t.visitor_id ORDER BY t.id')]
    calls=[list(r) for r in c.execute('SELECT id,phone,caller,at,duration,spoken_by,kind,remarks,created_at,staff,updated_at,updated_by,version FROM calls ORDER BY id')]
    audit=[list(r) for r in c.execute('SELECT id,username,login_at,logout_at,last_seen,end_reason FROM sessions_log ORDER BY id')]
    c.rollback()
    return workbook([
      ('Visitors',[['Visitor ID','Name','Mobile','CNIC']]+people),
      ('Visits',[['Visit ID','Visitor ID','Name','Mobile','CNIC','IN time (PKT)','OUT time (PKT)','Meeting with','Purpose','Recorded by','Remarks','OUT by','Updated at','Updated by','Version']]+visits),
      ('Telephone Callbacks',[['Call ID','Phone','Caller','Call time (PKT)','Duration (seconds)','Spoken by','Type','Remarks','Saved at (PKT)','Recorded by','Updated at','Updated by','Version']]+calls),
      ('Login Activity',[['Session ID','Login ID','Sign-in (PKT)','Sign-out (PKT)','Last seen (PKT)','End reason']]+audit)])


def history_export(c):
    c.execute('BEGIN')
    sessions=[list(r) for r in c.execute('SELECT id,username,login_at,logout_at,last_seen,end_reason FROM sessions_log ORDER BY id')]
    changes=[list(r) for r in c.execute('SELECT id,at,staff,action,entity,record_id,before_json,after_json FROM change_log ORDER BY id')]
    c.rollback()
    return workbook([('Login Logout History',[['Session ID','Login ID','Sign-in (PKT)','Sign-out (PKT)','Last seen (PKT)','End reason']]+sessions),('Record Change History',[['Change ID','Time (PKT)','Staff login','Action','Record type','Record ID','Before (JSON)','After (JSON)']]+changes)])
