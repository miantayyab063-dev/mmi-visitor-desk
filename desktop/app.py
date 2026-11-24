"""MMI Visitor Register — Python 3.10+, no third-party dependencies."""
import os, json, sqlite3, re, secrets, hashlib, hmac, time, io, csv, argparse, webbrowser, threading
from pathlib import Path
import excel_backup
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlsplit, parse_qs
ROOT=Path(__file__).resolve().parent
DATA=Path(os.environ.get('MMI_DATA_DIR',str(ROOT/'data')))
TZ=timezone(timedelta(hours=5))
STARTED=datetime.now(TZ).isoformat(timespec="seconds")
SESSIONS={}; ATTEMPTS={}; LOCK=threading.RLock()
@contextmanager
def db():
    c=sqlite3.connect(DATA/'mmi.sqlite3',timeout=10)
    c.row_factory=sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    c.execute('PRAGMA synchronous=FULL')
    try:
        with c:yield c
    finally:c.close()
def init():
    DATA.mkdir(parents=True,exist_ok=True,mode=0o700)
    if os.name=='posix':os.chmod(DATA,0o700)
    with db() as c:
        c.execute('PRAGMA journal_mode=WAL')
        c.executescript('''CREATE TABLE IF NOT EXISTS visitors(id INTEGER PRIMARY KEY,name TEXT NOT NULL,mobile TEXT NOT NULL UNIQUE,cnic TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS visits(id INTEGER PRIMARY KEY,visitor_id INTEGER NOT NULL REFERENCES visitors(id),at TEXT NOT NULL,purpose TEXT NOT NULL,token TEXT NOT NULL UNIQUE);
CREATE INDEX IF NOT EXISTS visit_at ON visits(at);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);''')
        for col,definition in [('out_at','TEXT'),('host','TEXT NOT NULL DEFAULT ""'),('staff','TEXT NOT NULL DEFAULT ""')]:
            if col not in [r[1] for r in c.execute('PRAGMA table_info(visits)')]: c.execute('ALTER TABLE visits ADD COLUMN '+col+' '+definition)
        c.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT UNIQUE NOT NULL,name TEXT NOT NULL,role TEXT NOT NULL,salt TEXT NOT NULL,hash TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS sessions_log(id INTEGER PRIMARY KEY,username TEXT,login_at TEXT,logout_at TEXT);
CREATE TABLE IF NOT EXISTS calls(id INTEGER PRIMARY KEY,phone TEXT NOT NULL,caller TEXT NOT NULL,at TEXT NOT NULL,duration INTEGER NOT NULL,remarks TEXT NOT NULL,spoken_by TEXT NOT NULL,kind TEXT NOT NULL,created_at TEXT NOT NULL,staff TEXT NOT NULL,token TEXT NOT NULL UNIQUE);''')
        # Old visits cannot be assumed to still be in the office. Mark only historic migration rows as closed, preserving unknown OUT time.
        c.execute("INSERT OR IGNORE INTO settings VALUES('version','2')")
        c.execute('CREATE INDEX IF NOT EXISTS visits_person ON visits(visitor_id,at)')
        c.execute("CREATE INDEX IF NOT EXISTS visits_open ON visits(visitor_id) WHERE out_at IS NULL AND staff<>''")
        c.execute('CREATE INDEX IF NOT EXISTS calls_time ON calls(at DESC,id DESC)')
        c.execute('CREATE INDEX IF NOT EXISTS calls_phone ON calls(phone,id DESC)')
        c.execute('CREATE INDEX IF NOT EXISTS calls_day ON calls(substr(at,1,10))')
        if os.name=='posix':os.chmod(DATA/'mmi.sqlite3',0o600)
        c.execute('CREATE INDEX IF NOT EXISTS visits_day ON visits(substr(at,1,10))')
        for table,columns in {
            'visitors':[('version','INTEGER NOT NULL DEFAULT 1')],
            'visits':[('remarks','TEXT NOT NULL DEFAULT ""'),('out_by','TEXT NOT NULL DEFAULT ""'),('updated_at','TEXT'),('updated_by','TEXT NOT NULL DEFAULT ""'),('version','INTEGER NOT NULL DEFAULT 1'),('snapshot_name','TEXT'),('snapshot_mobile','TEXT'),('snapshot_cnic','TEXT')],
            'sessions_log':[('last_seen','TEXT'),('end_reason','TEXT')],
            'calls':[('version','INTEGER NOT NULL DEFAULT 1'),('updated_at','TEXT'),('updated_by','TEXT NOT NULL DEFAULT ""')]
        }.items():
            present={r[1] for r in c.execute('PRAGMA table_info('+table+')')}
            for column,definition in columns:
                if column not in present:c.execute('ALTER TABLE '+table+' ADD COLUMN '+column+' '+definition)
        c.execute('UPDATE visits SET snapshot_name=(SELECT name FROM visitors WHERE id=visits.visitor_id), snapshot_mobile=(SELECT mobile FROM visitors WHERE id=visits.visitor_id), snapshot_cnic=(SELECT cnic FROM visitors WHERE id=visits.visitor_id) WHERE snapshot_name IS NULL')
        c.execute("UPDATE sessions_log SET end_reason='Server restarted; exact logout unknown' WHERE logout_at IS NULL AND end_reason IS NULL")
        c.executescript('''CREATE TABLE IF NOT EXISTS change_log(id INTEGER PRIMARY KEY,at TEXT NOT NULL,staff TEXT NOT NULL,action TEXT NOT NULL,entity TEXT NOT NULL,record_id INTEGER NOT NULL,before_json TEXT,after_json TEXT);
CREATE TRIGGER IF NOT EXISTS protect_history_update BEFORE UPDATE ON change_log BEGIN SELECT RAISE(ABORT,'History is append-only'); END;
CREATE TRIGGER IF NOT EXISTS protect_history_delete BEFORE DELETE ON change_log BEGIN SELECT RAISE(ABORT,'History is append-only'); END;''')
        for row in c.execute("SELECT * FROM calls WHERE (length(phone)=12 AND substr(phone,1,2)='92') OR (length(phone)=14 AND substr(phone,1,4)='0092')").fetchall():
            try:normalized=mobile(row['phone'])
            except ValueError:continue
            c.execute('UPDATE calls SET phone=? WHERE id=?',(normalized,row['id']))
            audit(c,'system','Phone format normalized during upgrade','call',row['id'],dict(row),dict(c.execute('SELECT * FROM calls WHERE id=?',(row['id'],)).fetchone()))

def audit(c,staff,action,entity,record_id,before=None,after=None):
    c.execute('INSERT INTO change_log(at,staff,action,entity,record_id,before_json,after_json) VALUES(?,?,?,?,?,?,?)',(now(),staff,action,entity,record_id,json.dumps(before,ensure_ascii=False) if before is not None else None,json.dumps(after,ensure_ascii=False) if after is not None else None))
def refresh_backups():
    with LOCK,db() as c:
        complete=excel_backup.export(c)
        history=excel_backup.history_export(c)
        folder=DATA/'backups';folder.mkdir(exist_ok=True)
        for name,content in [('MMI_All_Records.xlsx',complete),('MMI_Login_Change_History.xlsx',history)]:
            temp=folder/(name+'.tmp')
            with temp.open('wb') as f:f.write(content);f.flush();os.fsync(f.fileno())
            os.replace(temp,folder/name)

def now():return datetime.now(TZ).isoformat(timespec='seconds')
def digits(s): return re.sub(r'[^0-9]','',str(s))
def mobile(s):
    s=digits(s)
    if s.startswith('0092'): s='0'+s[4:]
    elif s.startswith('92') and len(s)==12: s='0'+s[2:]
    if not re.fullmatch(r'03\d{9}',s): raise ValueError('Enter Pakistani mobile: 03XXXXXXXXX or +923XXXXXXXXX.')
    return s
def record(d):
    m=mobile(d.get('mobile','')); n=str(d.get('name','')).strip(); cn=digits(d.get('cnic','')); p=str(d.get('purpose','')).strip(); host=str(d.get('host','')).strip()[:150]; staff=str(d.get('_staff','')).strip()
    if not 2<=len(n)<=100: raise ValueError('Name must be 2–100 characters.')
    if len(cn)!=13: raise ValueError('CNIC must contain exactly 13 digits.')
    if len(p)>500: raise ValueError('Purpose is too long (maximum 500).')
    remarks=str(d.get('remarks','')).strip()
    if len(remarks)>4000:raise ValueError('Remarks maximum 4000 characters.')
    token=str(d.get('token',''))
    if not re.fullmatch(r'[a-zA-Z0-9-]{16,100}',token): raise ValueError('Please refresh and try again.')
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        old=c.execute('SELECT id FROM visits WHERE token=?',(token,)).fetchone()
        if old:return {'message':'Visit already saved.','id':old['id']}
        selected=int(d.get('visitor_id') or 0)
        if selected:
            v=c.execute('SELECT * FROM visitors WHERE id=?',(selected,)).fetchone()
            if not v:raise ValueError('Selected visitor no longer exists.')
            if int(d.get('profile_version',0))!=v['version']:raise ValueError('Visitor changed on another screen. Search and select again.')
            rows=[v];vid=v['id']
            conflict=c.execute('SELECT 1 FROM visitors WHERE id<>? AND (mobile=? OR cnic=?)',(vid,m,cn)).fetchone()
            if conflict:raise ValueError('Mobile or CNIC belongs to another visitor.')
            if (v['name'],v['mobile'],v['cnic'])!=(n,m,cn):
                before=dict(v);c.execute('UPDATE visitors SET name=?,mobile=?,cnic=?,version=version+1 WHERE id=?',(n,m,cn,vid));audit(c,staff,'Profile updated','visitor',vid,before,dict(c.execute('SELECT * FROM visitors WHERE id=?',(vid,)).fetchone()))
        else:
            rows=c.execute('SELECT * FROM visitors WHERE mobile=? OR cnic=?',(m,cn)).fetchall()
            if rows:
                if len(rows)>1 or rows[0]['mobile']!=m or rows[0]['cnic']!=cn:raise ValueError('Mobile/CNIC conflicts with an existing record. Select the correct saved visitor.')
                v=rows[0];vid=v['id']
                if n.casefold()!=v['name'].casefold():raise ValueError('Select this saved visitor before changing the name.')
            else:
                vid=c.execute('INSERT INTO visitors(name,mobile,cnic) VALUES(?,?,?)',(n,m,cn)).lastrowid
                audit(c,staff,'Profile created','visitor',vid,after={'name':n,'mobile':m,'cnic':cn})
        active=c.execute("SELECT id FROM visits WHERE visitor_id=? AND out_at IS NULL AND staff<>''",(vid,)).fetchone()
        if active:raise ValueError('Visitor is already IN. Mark the open visit OUT first.')
        at=now()
        visit=c.execute('INSERT INTO visits(visitor_id,at,purpose,token,host,staff,remarks,snapshot_name,snapshot_mobile,snapshot_cnic) VALUES(?,?,?,?,?,?,?,?,?,?)',(vid,at,p,token,host,staff,remarks,n,m,cn)).lastrowid
        audit(c,staff,'IN','visit',visit,after=dict(c.execute('SELECT * FROM visits WHERE id=?',(visit,)).fetchone()))
    return {'message':'Return visit saved.' if rows else 'New visitor and first visit saved.','id':visit,'at':at}
def password(p,s):return hashlib.pbkdf2_hmac('sha256',p.encode(),bytes.fromhex(s),240000).hex()
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def send(self,status,obj,kind='application/json',extra=None):
        if self.command=='POST' and status==200:
            try:refresh_backups()
            except Exception:
                if isinstance(obj,dict):obj['backup_warning']='Database saved, but Excel backup could not be updated. Close the Excel backup file and check free disk space.'
        raw=json.dumps(obj).encode() if kind=='application/json' else (obj.encode() if isinstance(obj,str) else obj)
        self.send_response(status); self.send_header('Content-Type',kind+'; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','DENY');self.send_header('Referrer-Policy','no-referrer');self.send_header('Permissions-Policy','camera=(), microphone=(), geolocation=()');self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; frame-ancestors 'none'")
        if os.environ.get('MMI_SECURE_COOKIE')=='1':self.send_header('Strict-Transport-Security','max-age=31536000')
        for k,v in (extra or {}).items():self.send_header(k,v)
        self.end_headers();self.wfile.write(raw)
    def trusted_request(self):
        host=self.headers.get('Host','').split(':')[0].lower()
        allowed={v.strip().lower() for v in os.environ.get('MMI_ALLOWED_HOSTS','127.0.0.1,localhost').split(',')}
        if host not in allowed:return False
        origin=self.headers.get('Origin')
        if origin:
            public=os.environ.get('MMI_PUBLIC_ORIGIN','').rstrip('/')
            if public:
                if origin!=public:return False
            elif urlsplit(origin).netloc!=self.headers.get('Host'):return False
        return True
    def session(self):
        cookies=dict(x.strip().split('=',1) for x in self.headers.get('Cookie','').split(';') if '=' in x)
        token=cookies.get('mmi','');entry=SESSIONS.get(token)
        if not entry:return None
        with db() as c:
            if entry['expires']<time.time() or time.time()-entry.get('activity',time.time())>1800:
                c.execute("UPDATE sessions_log SET end_reason='Session expired',last_seen=COALESCE(last_seen,login_at) WHERE id=?",(entry['logid'],));SESSIONS.pop(token,None);return None
            u=c.execute('SELECT id,username,name,role FROM users WHERE id=? AND active=1',(entry['uid'],)).fetchone()
            if not u:return None
            if urlsplit(self.path).path!='/api/health':
                entry['activity']=time.time()
                c.execute('UPDATE sessions_log SET last_seen=? WHERE id=?',(now(),entry['logid']))
            result=dict(u);result['login_at']=entry['login_at']
            result['previous_login']=c.execute('SELECT login_at,logout_at,last_seen,end_reason FROM sessions_log WHERE username=? AND id<>? ORDER BY id DESC LIMIT 1',(u['username'],entry['logid'])).fetchone()
            result['previous_login']=dict(result['previous_login']) if result['previous_login'] else None
            return result
    def do_GET(self):
        try:self.handle_get()
        except (ValueError,TypeError):self.send(400,{'error':'Invalid request parameters.'})
        except sqlite3.Error:self.send(503,{'error':'Database unavailable. Check disk space and access permissions.'})
        except (BrokenPipeError,ConnectionResetError):pass
        except Exception:self.send(500,{'error':'Unable to load records. Please retry.'})
    def handle_get(self):
        if not self.trusted_request():return self.send(403,{'error':'Untrusted host or origin.'})
        u=urlsplit(self.path);q=parse_qs(u.query)
        if u.path in ('/','/app.js','/style.css','/print.js'):
            name={'/':'index.html','/app.js':'app.js','/style.css':'style.css','/print.js':'print.js'}[u.path]
            return self.send(200,(ROOT/'static'/name).read_bytes(),{'index.html':'text/html','app.js':'text/javascript','style.css':'text/css','print.js':'text/javascript'}[name])
        if u.path=='/api/status':
            with db() as c: configured=bool(c.execute('SELECT 1 FROM users').fetchone()); upgrade=bool(c.execute("SELECT 1 FROM settings WHERE key='auth'").fetchone())
            return self.send(200,{'configured':configured,'loggedIn':bool(self.session()),'user':self.session(),'started':STARTED,'serverTime':now(),'upgrade':upgrade})
        user=self.session()
        if not user:return self.send(401,{'error':'Please sign in.'})
        with db() as c:
            if u.path=='/api/health':
                try:
                    c.execute('BEGIN IMMEDIATE')
                    c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('health_check',?)",(now(),))
                    c.commit()
                    return self.send(200,{'ok':True,'checked_at':now()})
                except sqlite3.Error:
                    return self.send(503,{'error':'Database write check failed.'})
            if u.path=='/api/users':
                if user['role']!='admin':return self.send(403,{'error':'Admin only.'})
                return self.send(200,[dict(r) for r in c.execute('SELECT id,username,name,role,active FROM users ORDER BY id')])
            if u.path=='/api/audit':
                if user['role']!='admin':return self.send(403,{'error':'Admin only.'})
                return self.send(200,[dict(r) for r in c.execute('SELECT * FROM sessions_log ORDER BY id DESC LIMIT 100')])
            if u.path=='/api/caller-search':
                term=q.get('q',[''])[0].strip()[:100];mode=q.get('mode',['phone'])[0];page=max(1,int(q.get('page',['1'])[0]));num=digits(term)
                if num.startswith('0092'):num='0'+num[4:]
                elif num.startswith('92'):num='0'+num[2:]
                if not term:return self.send(200,{'rows':[],'total':0})
                # Latest call details per number; visitor directory fills gaps.
                source="(SELECT phone,caller FROM calls c1 WHERE id=(SELECT max(id) FROM calls c2 WHERE c2.phone=c1.phone) UNION ALL SELECT mobile phone,name caller FROM visitors WHERE mobile NOT IN (SELECT phone FROM calls))"
                condition='phone GLOB ?' if mode=='phone' else 'instr(lower(caller),lower(?))>0';arg=num+'*' if mode=='phone' and num else ('no-match' if mode=='phone' else term)
                total=c.execute('SELECT count(*) FROM '+source+' WHERE '+condition,(arg,)).fetchone()[0]
                found=c.execute('SELECT phone,caller FROM '+source+' WHERE '+condition+' ORDER BY phone LIMIT 30 OFFSET ?',(arg,(page-1)*30)).fetchall();result=[]
                for row in found:
                    item=dict(row);last=c.execute('SELECT at,remarks,kind,spoken_by,staff FROM calls WHERE phone=? ORDER BY id DESC LIMIT 1',(row['phone'],)).fetchone();item['last_details']=dict(last) if last else None;result.append(item)
                return self.send(200,{'rows':result,'total':total})
            if u.path in ('/api/calls','/api/call-export','/api/call-print'):
                term=q.get('q',[''])[0].strip()[:100];day=q.get('date',[''])[0]
                if re.fullmatch(r'[+0-9 ()-]+',term or 'x'):
                    term=digits(term)
                    if term.startswith('0092'):term='0'+term[4:]
                    elif term.startswith('92') and len(term)<=12:term='0'+term[2:]
                where=" WHERE (?='' OR instr(phone,?)>0 OR instr(lower(caller),lower(?))>0 OR instr(lower(remarks),lower(?))>0 OR instr(lower(spoken_by),lower(?))>0 OR instr(lower(staff),lower(?))>0) AND (?='' OR substr(at,1,10)=?)"
                args=(term,term,term,term,term,term,day,day)
                columns='id,phone,caller,at,duration,spoken_by,kind,remarks,created_at,staff,updated_at,updated_by,version'
                headers=['Call ID','Phone','Caller','Call time (PKT)','Duration (seconds)','Handled by','Type','Remarks','Saved at (PKT)','Saved by','Updated at','Updated by','Version']
                if u.path=='/api/call-export':
                    rows=c.execute('SELECT '+columns+' FROM calls'+where+' ORDER BY at DESC,id DESC',args).fetchall();output=io.StringIO();writer=csv.writer(output);writer.writerow(headers)
                    for row in rows:writer.writerow([("'"+str(value)) if str(value).startswith(('=','+','-','@')) else value for value in row])
                    return self.send(200,'\ufeff'+output.getvalue(),'text/csv',{'Content-Disposition':'attachment; filename="MMI-callback-records.csv"'})
                if u.path=='/api/call-print':
                    from html import escape
                    rows=c.execute('SELECT '+columns+' FROM calls'+where+' ORDER BY at DESC,id DESC',args).fetchall()
                    html='<!doctype html><html><meta charset="utf-8"><title>MMI Call History</title><link rel="stylesheet" href="/style.css"><body class="printView"><h1>MMI — Telephone &amp; Callback History</h1><p>Generated '+escape(now())+' · '+escape(user['username'])+' · '+str(len(rows))+' records</p><button id="printNow">Print / Save PDF</button><table><thead><tr>'+''.join('<th>'+h+'</th>' for h in headers)+'</tr></thead><tbody>'
                    for row in rows:html+='<tr>'+''.join('<td>'+escape(str(value if value is not None else ''))+'</td>' for value in row)+'</tr>'
                    html+='</tbody></table><p class="print-credit">Developed by mianmuhamamdtayyab</p><script src="/print.js"></script></body></html>'
                    return self.send(200,html,'text/html')
                page=max(1,int(q.get('page',['1'])[0]));size=30 if q.get('paged') else 500
                total=c.execute('SELECT count(*) FROM calls'+where,args).fetchone()[0]
                rows=c.execute('SELECT * FROM calls'+where+' ORDER BY at DESC,id DESC LIMIT ? OFFSET ?',args+(size,(page-1)*size)).fetchall()
                return self.send(200,{'rows':[dict(r) for r in rows],'total':total} if q.get('paged') else [dict(r) for r in rows])
            if u.path=='/api/search':
                term=q.get('q',[''])[0].strip()[:100];num=digits(term);mode=q.get('mode',['auto'])[0];page=max(1,int(q.get('page',['1'])[0]))
                if num.startswith('0092'):num='0'+num[4:]
                elif num.startswith('92'):num='0'+num[2:]
                if not term:return self.send(200,{'rows':[],'total':0} if q.get('paged') else [])
                if mode=='phone':where='v.mobile GLOB ?';args=(num+'*',) if num else ('no-match',)
                elif mode=='cnic':where='v.cnic GLOB ?';args=(num+'*',) if num else ('no-match',)
                elif num and re.fullmatch(r'[+0-9 ()-]+',term):where='v.cnic GLOB ?' if len(num)>11 else 'v.mobile GLOB ?';args=(num+'*',)
                else:where='instr(lower(v.name),lower(?))>0';args=(term,)
                total=c.execute('SELECT count(*) FROM visitors v WHERE '+where,args).fetchone()[0]
                rows=c.execute('SELECT v.*,(SELECT count(*) FROM visits t WHERE t.visitor_id=v.id) visits,(SELECT max(at) FROM visits t WHERE t.visitor_id=v.id) last_visit FROM visitors v WHERE '+where+' ORDER BY v.mobile,v.id LIMIT 30 OFFSET ?',args+((page-1)*30,)).fetchall()
                result=[]
                for row in rows:
                    item=dict(row);last=c.execute('SELECT id,host,purpose,remarks,at,out_at,staff FROM visits WHERE visitor_id=? ORDER BY id DESC LIMIT 1',(row['id'],)).fetchone();item['last_details']=dict(last) if last else None;result.append(item)
                return self.send(200,{'rows':result,'total':total} if q.get('paged') else result)
            if u.path in ('/api/visits','/api/export','/api/print'):
                day=q.get('date',[''])[0];term=q.get('q',[''])[0][:100];vid=q.get('visitor',[''])[0]
                if re.fullmatch(r'[+0-9 ()-]+',term or 'x'):
                    term=digits(term)
                    if term.startswith('0092'):term='0'+term[4:]
                    elif term.startswith('92') and len(term)<=12:term='0'+term[2:]
                where=' WHERE (?=\'\' OR substr(t.at,1,10)=?) AND (?=\'\' OR instr(lower(v.name),lower(?))>0 OR instr(v.mobile,?)>0 OR instr(v.cnic,?)>0 OR v.id IN (SELECT visitor_id FROM visits WHERE instr(lower(snapshot_name),lower(?))>0 OR instr(snapshot_mobile,?)>0 OR instr(snapshot_cnic,?)>0)) AND (?=\'\' OR v.id=?)'
                args=(day,day,term,term,term,term,term,term,term,vid,vid)
                base=' FROM visits t JOIN visitors v ON v.id=t.visitor_id'
                select='SELECT t.id,t.visitor_id,t.snapshot_name name,t.snapshot_mobile mobile,t.snapshot_cnic cnic,t.at,t.purpose,t.out_at,t.host,t.staff,t.remarks,t.out_by,t.updated_at,t.updated_by,t.version'
                if u.path=='/api/print':
                    from html import escape
                    rows=c.execute(select+base+where+' ORDER BY t.id DESC',args).fetchall()
                    headers=['Visit ID','Visitor ID','Name','Mobile','CNIC','IN (PKT)','Purpose','OUT (PKT)','Meeting with','Saved by','Remarks','OUT by','Updated at','Updated by','Version']
                    html='<!doctype html><html><meta charset="utf-8"><title>MMI Visitor History</title><link rel="stylesheet" href="/style.css"><body class="printView"><h1>MMI — Visitor History</h1><p>Generated '+escape(now())+' · '+escape(user['username'])+' · '+str(len(rows))+' records</p><button id="printNow">Print / Save PDF</button><table><thead><tr>'+''.join('<th>'+h+'</th>' for h in headers)+'</tr></thead><tbody>'
                    for row in rows:html+='<tr>'+''.join('<td>'+escape(str(value if value is not None else ''))+'</td>' for value in row)+'</tr>'
                    html+='</tbody></table><p class="print-credit">Developed by mianmuhamamdtayyab</p><script src="/print.js"></script></body></html>'
                    return self.send(200,html,'text/html')
                if u.path=='/api/export':
                    rows=c.execute(select+base+where+' ORDER BY t.id DESC',args).fetchall();s=io.StringIO();w=csv.writer(s);w.writerow(['Visit ID','Visitor ID','Name','Mobile','CNIC','IN (PKT)','Purpose','OUT (PKT)','Meeting with','Saved by','Remarks','OUT by','Updated at','Updated by','Version'])
                    for r in rows:w.writerow([("'"+str(x)) if str(x).startswith(('=','+','-','@')) else x for x in r])
                    return self.send(200,'\ufeff'+s.getvalue(),'text/csv',{'Content-Disposition':'attachment; filename="MMI-visits.csv"'})
                page=max(1,min(100000,int(q.get('page',['1'])[0])));count=c.execute('SELECT count(*)'+base+where,args).fetchone()[0]
                rows=c.execute(select+base+where+' ORDER BY t.id DESC LIMIT 30 OFFSET ?',args+((page-1)*30,)).fetchall()
                today=datetime.now(TZ).date().isoformat()
                stats={'today':c.execute('SELECT count(*) FROM visits WHERE substr(at,1,10)=?',(today,)).fetchone()[0],'people':c.execute('SELECT count(*) FROM visitors').fetchone()[0],'visits':c.execute('SELECT count(*) FROM visits').fetchone()[0],'inside':c.execute("SELECT count(*) FROM visits WHERE out_at IS NULL AND staff<>''").fetchone()[0]}
                return self.send(200,{'rows':[dict(r) for r in rows],'total':count,'stats':stats})
            if u.path=='/api/history-backup':
                if user['role']!='admin':return self.send(403,{'error':'Admin only.'})
                return self.send(200,excel_backup.history_export(c),'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',{'Content-Disposition':'attachment; filename="MMI_Login_Change_History.xlsx"'})
            if u.path=='/api/changes':
                rows=c.execute('SELECT * FROM change_log WHERE entity=? AND record_id=? ORDER BY id DESC',(q.get('entity',['visit'])[0],int(q.get('id',['0'])[0]))).fetchall()
                return self.send(200,[dict(r) for r in rows])
            if u.path=='/api/backup':
                if user['role']!='admin':return self.send(403,{'error':'Admin only. Receptionist can print or export visit history.'})
                content=excel_backup.export(c)
                return self.send(200,content,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',{'Content-Disposition':'attachment; filename="MMI_All_Records.xlsx"'})
            if u.path=='/api/database-backup':
                if user['role']!='admin':return self.send(403,{'error':'Admin only.'})
                import tempfile
                with tempfile.TemporaryDirectory() as temp:
                    path=Path(temp)/'backup.sqlite3';dest=sqlite3.connect(path);c.backup(dest);dest.close()
                    return self.send(200,path.read_bytes(),'application/octet-stream',{'Content-Disposition':'attachment; filename="MMI-backup.sqlite3"'})
        self.send(404,{'error':'Not found.'})
    def do_POST(self):
        try:
            if not self.trusted_request():return self.send(403,{'error':'Untrusted host or origin.'})
            # Custom header blocks cross-origin form submissions; no CORS enabled.
            if self.headers.get('X-MMI')!='1':return self.send(403,{'error':'Invalid request.'})
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=8192:raise ValueError('Invalid request size.')
            d=json.loads(self.rfile.read(length))
            if not isinstance(d,dict):raise ValueError('Request must be a JSON object.')
            path=urlsplit(self.path).path
            if path in ('/api/setup','/api/login'):
                with LOCK,db() as c:
                    key=self.client_address[0];attempt=ATTEMPTS.get(key,(0,0))
                    if attempt[0]>=8 and time.time()-attempt[1]<300:return self.send(429,{'error':'Too many attempts. Wait five minutes.'})
                    username=str(d.get('username','')).strip().lower();p=str(d.get('password',''))
                    if path=='/api/setup':
                        if os.environ.get('MMI_SETUP_DISABLED')=='1':raise ValueError('Website setup is disabled. Initialize admin locally first.')
                        c.execute('BEGIN IMMEDIATE')
                        if c.execute('SELECT 1 FROM users').fetchone():raise ValueError('Already configured.')
                        if key not in ('127.0.0.1','::1'):raise ValueError('Complete first setup on the server computer.')
                        if not re.fullmatch(r'[a-z0-9_.-]{3,40}',username):raise ValueError('Login ID: 3–40 letters, digits, dot, dash or underscore.')
                        if len(p)<10:raise ValueError('Password must be at least 10 characters.')
                        old=c.execute("SELECT value FROM settings WHERE key='auth'").fetchone()
                        if old:
                            salt,hashed=json.loads(old[0])
                            if not hmac.compare_digest(password(str(d.get('old_password','')),salt),hashed):raise ValueError('Enter the previous MMI office password to upgrade.')
                        salt=secrets.token_hex(16);uid=c.execute('INSERT INTO users(username,name,role,salt,hash) VALUES(?,?,?,?,?)',(username,str(d.get('name','Administrator'))[:100] or 'Administrator','admin',salt,password(p,salt))).lastrowid
                    else:
                        row=c.execute('SELECT * FROM users WHERE username=? AND active=1',(username,)).fetchone()
                        candidate=password(p,row['salt'] if row else '00'*16)
                        if not row or not hmac.compare_digest(candidate,row['hash']):
                            ATTEMPTS[key]=(attempt[0]+1,time.time());return self.send(403,{'error':'Incorrect login ID or password.'})
                        uid=row['id']
                    ATTEMPTS.pop(key,None);token=secrets.token_urlsafe(32)
                    logid=c.execute('INSERT INTO sessions_log(username,login_at,last_seen) SELECT username,?,? FROM users WHERE id=?',(now(),now(),uid)).lastrowid
                    SESSIONS[token]={'uid':uid,'expires':time.time()+43200,'logid':logid,'login_at':now(),'activity':time.time()}
                secure='; Secure' if os.environ.get('MMI_SECURE_COOKIE')=='1' else ''
                return self.send(200,{'ok':True},extra={'Set-Cookie':f'mmi={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200'+secure})
            user=self.session()
            if not user:return self.send(401,{'error':'Please sign in.'})
            if path=='/api/visit':
                d['_staff']=user['username'];return self.send(200,record(d))
            if path=='/api/out':
                with db() as c:
                    c.execute('BEGIN IMMEDIATE');row=c.execute('SELECT * FROM visits WHERE id=?',(int(d.get('id',0)),)).fetchone()
                    if not row:raise ValueError('Visit not found.')
                    if not row['staff']:raise ValueError('Historic visit: original OUT time is unknown.')
                    if not row['out_at']:
                        c.execute('UPDATE visits SET out_at=?,out_by=?,version=version+1 WHERE id=?',(now(),user['username'],row['id']))
                        audit(c,user['username'],'OUT','visit',row['id'],dict(row),dict(c.execute('SELECT * FROM visits WHERE id=?',(row['id'],)).fetchone()))
                return self.send(200,{'message':'Visitor marked OUT.'})
            if path=='/api/edit-visit':
                host=str(d.get('host','')).strip();purpose=str(d.get('purpose','')).strip();remarks=str(d.get('remarks','')).strip();reason=str(d.get('reason','')).strip()
                if len(host)>150 or len(purpose)>500 or len(remarks)>4000 or not 3<=len(reason)<=500:raise ValueError('Add a correction reason and check field lengths.')
                with db() as c:
                    c.execute('BEGIN IMMEDIATE');old=c.execute('SELECT * FROM visits WHERE id=?',(int(d.get('id',0)),)).fetchone()
                    if not old:raise ValueError('Visit not found.')
                    if old['version']!=int(d.get('version',0)):raise ValueError('Record changed elsewhere. Reload before editing.')
                    c.execute('UPDATE visits SET host=?,purpose=?,remarks=?,updated_at=?,updated_by=?,version=version+1 WHERE id=?',(host,purpose,remarks,now(),user['username'],old['id']))
                    audit(c,user['username'],'Visit corrected: '+reason,'visit',old['id'],dict(old),dict(c.execute('SELECT * FROM visits WHERE id=?',(old['id'],)).fetchone()))
                return self.send(200,{'message':'Visit details updated; original change history preserved.'})
            if path=='/api/profile':
                n=str(d.get('name','')).strip();m=mobile(d.get('mobile',''));cn=digits(d.get('cnic',''));reason=str(d.get('reason','')).strip()
                if not 2<=len(n)<=100 or len(cn)!=13 or not 3<=len(reason)<=500:raise ValueError('Check name, CNIC and correction reason.')
                with db() as c:
                    c.execute('BEGIN IMMEDIATE');old=c.execute('SELECT * FROM visitors WHERE id=?',(int(d.get('id',0)),)).fetchone()
                    if not old:raise ValueError('Visitor not found.')
                    if old['version']!=int(d.get('version',0)):raise ValueError('Profile changed elsewhere. Search/select again.')
                    if c.execute('SELECT 1 FROM visitors WHERE id<>? AND (mobile=? OR cnic=?)',(old['id'],m,cn)).fetchone():raise ValueError('Mobile or CNIC belongs to another visitor.')
                    c.execute('UPDATE visitors SET name=?,mobile=?,cnic=?,version=version+1 WHERE id=?',(n,m,cn,old['id']))
                    audit(c,user['username'],'Profile corrected: '+reason,'visitor',old['id'],dict(old),dict(c.execute('SELECT * FROM visitors WHERE id=?',(old['id'],)).fetchone()))
                return self.send(200,{'message':'Profile updated. Past visits retain their original identity details.'})
            if path=='/api/user':
                if user['role']!='admin':return self.send(403,{'error':'Admin only.'})
                username=str(d.get('username','')).strip().lower();name=str(d.get('name','')).strip();p=str(d.get('password',''));role=d.get('role','receptionist')
                if not re.fullmatch(r'[a-z0-9_.-]{3,40}',username) or not name or len(name)>100 or role not in ('admin','receptionist'):raise ValueError('Enter valid login ID, name and role.')
                with LOCK,db() as c:
                    c.execute('BEGIN IMMEDIATE');old=c.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone()
                    active=int(bool(d.get('active',True)))
                    if old and old['id']==user['id'] and (not active or role!='admin'):raise ValueError('You cannot disable or demote your own account.')
                    if not old or p:
                        if len(p)<10:raise ValueError('Password must be at least 10 characters.')
                    if old:
                        c.execute('UPDATE users SET name=?,role=?,active=? WHERE id=?',(name,role,active,old['id']))
                        if p:
                            salt=secrets.token_hex(16);c.execute('UPDATE users SET salt=?,hash=? WHERE id=?',(salt,password(p,salt),old['id']))
                            with LOCK:
                                for k in list(SESSIONS):
                                    if SESSIONS[k]['uid']==old['id']:
                                        expired=SESSIONS.pop(k,None);c.execute("UPDATE sessions_log SET end_reason='Password reset' WHERE id=?",(expired['logid'],))
                    else:
                        salt=secrets.token_hex(16);c.execute('INSERT INTO users(username,name,role,salt,hash,active) VALUES(?,?,?,?,?,?)',(username,name,role,salt,password(p,salt),active))
                    if not active:c.execute("UPDATE sessions_log SET end_reason='Account disabled' WHERE username=? AND logout_at IS NULL",(username,))
                    audit(c,user['username'],'Account updated','user',old['id'] if old else c.execute('SELECT id FROM users WHERE username=?',(username,)).fetchone()[0],after={'username':username,'name':name,'role':role,'active':active,'password_reset':bool(p)})
                return self.send(200,{'message':'Login account saved.'})
            if path in ('/api/call','/api/edit-call'):
                phone=digits(d.get('phone',''))
                try:phone=mobile(phone)
                except ValueError:pass
                caller=str(d.get('caller','')).strip()[:100];remarks=str(d.get('remarks','')).strip();spoken=str(d.get('spoken_by','')).strip()[:100];kind=d.get('kind','Incoming');duration=int(d.get('duration',0));token=str(d.get('token',''))
                if not 6<=len(phone)<=18 or not spoken or len(remarks)>4000 or kind not in ('Incoming','Outgoing','Callback') or not 0<=duration<=604800 or not re.fullmatch(r'[a-zA-Z0-9-]{16,100}',token):raise ValueError('Check phone, staff, duration and remarks.')
                at=datetime.fromisoformat(str(d.get('at','')))
                if at.tzinfo is None:at=at.replace(tzinfo=TZ)
                with db() as c:
                    c.execute('BEGIN IMMEDIATE')
                    if path=='/api/edit-call':
                        previous=c.execute('SELECT * FROM calls WHERE id=?',(int(d.get('id',0)),)).fetchone();reason=str(d.get('reason','')).strip()
                        if not previous or previous['version']!=int(d.get('version',0)):raise ValueError('Call changed elsewhere or not found. Reload history.')
                        if not 3<=len(reason)<=500:raise ValueError('Add a correction reason.')
                        c.execute('UPDATE calls SET phone=?,caller=?,at=?,duration=?,remarks=?,spoken_by=?,kind=?,updated_at=?,updated_by=?,version=version+1 WHERE id=?',(phone,caller,at.astimezone(TZ).isoformat(timespec='seconds'),duration,remarks,spoken,kind,now(),user['username'],previous['id']))
                        audit(c,user['username'],'Call corrected: '+reason,'call',previous['id'],dict(previous),dict(c.execute('SELECT * FROM calls WHERE id=?',(previous['id'],)).fetchone()))
                    else:
                        cur=c.execute('INSERT INTO calls(phone,caller,at,duration,remarks,spoken_by,kind,created_at,staff,token) VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(token) DO NOTHING',(phone,caller,at.astimezone(TZ).isoformat(timespec='seconds'),duration,remarks,spoken,kind,now(),user['username'],token))
                        if cur.rowcount:audit(c,user['username'],'Call recorded','call',cur.lastrowid,after=dict(c.execute('SELECT * FROM calls WHERE id=?',(cur.lastrowid,)).fetchone()))
                return self.send(200,{'message':'Call record saved.'})
            if path=='/api/logout':
                with LOCK,db() as c:
                    for item in self.headers.get('Cookie','').split(';'):
                        if item.strip().startswith('mmi='):
                            entry=SESSIONS.pop(item.strip()[4:],None)
                            if entry:c.execute("UPDATE sessions_log SET logout_at=?,last_seen=?,end_reason='Signed out' WHERE id=?",(now(),now(),entry['logid']))
                return self.send(200,{'ok':True},extra={'Set-Cookie':'mmi=; Max-Age=0; Path=/'})
            self.send(404,{'error':'Not found.'})
        except (ValueError,TypeError,KeyError,sqlite3.IntegrityError) as e:self.send(400,{'error':str(e)})
        except Exception:self.send(500,{'error':'Unable to save. Check disk space and server console.'})
def main():
    p=argparse.ArgumentParser();p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=8765);p.add_argument('--no-browser',action='store_true');a=p.parse_args();init()
    try:refresh_backups()
    except OSError:print('Warning: Excel backup refresh failed. Close the backup file/check disk permissions.')
    server=ThreadingHTTPServer((a.host,a.port),Handler)
    print(f'MMI running at http://{a.host}:{a.port} | Data: {DATA} | Ctrl+C to stop')
    if not a.no_browser:threading.Timer(.6,lambda:webbrowser.open(f'http://127.0.0.1:{a.port}')).start()
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
if __name__=='__main__':main()
