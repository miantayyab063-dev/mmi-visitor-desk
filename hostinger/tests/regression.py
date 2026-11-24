import os,sys,subprocess,tempfile,shutil,socket,time,urllib.request,urllib.error,http.cookiejar,json,unittest,io,zipfile,sqlite3
from pathlib import Path
SRC=Path(__file__).resolve().parents[1]
PHP=os.environ.get('MMI_TEST_PHP','php');RUNTIME=Path(os.environ.get('MMI_TEST_MARIADB_BASE','/usr'));ENV=os.environ.copy();ENV['LD_LIBRARY_PATH']=str(RUNTIME/'lib/x86_64-linux-gnu')
TEMP=tempfile.TemporaryDirectory(prefix='mmi-hostinger-test-');ROOT=Path(TEMP.name);SITE=ROOT/'site';shutil.copytree(SRC,SITE,ignore=shutil.ignore_patterns('config.php','*.xlsx','__pycache__'))
def freeport():
 s=socket.socket();s.bind(('127.0.0.1',0));p=s.getsockname()[1];s.close();return p
DBPORT=freeport();PORT=freeport();BASE=f'http://127.0.0.1:{PORT}/mmi';DBNAME='mmi_test_isolated';KEY='local-installation-secret-for-tests-2026'
CONFIG={'db_host':'127.0.0.1','db_port':DBPORT,'db_name':DBNAME,'db_user':'root','db_password':'','app_url':BASE,'install_key':KEY,'allow_http':True}
(SITE/'mmi_private/config.php').write_text('<?php return json_decode('+json.dumps(json.dumps(CONFIG))+',true);')
DBLOG=(ROOT/'maria.log').open('wb');PHPLOG=(ROOT/'php.log').open('wb');DBPROC=None;WEBPROC=None

def phpcode(code):
 r=subprocess.run([PHP,'-r',code],capture_output=True,text=True,env=ENV)
 if r.returncode:raise RuntimeError(r.stderr+r.stdout)
 return r.stdout

def sql(query,dbname=DBNAME):
 return phpcode('$p=new PDO('+json.dumps(f'mysql:host=127.0.0.1;port={DBPORT};charset=utf8mb4')+',"root","");$p->setAttribute(PDO::ATTR_ERRMODE,PDO::ERRMODE_EXCEPTION);'+('$p->exec("USE `'+dbname+'`");' if dbname else '')+'$p->exec('+json.dumps(query)+');')
def query(sqltext):
 return json.loads(phpcode('$p=new PDO('+json.dumps(f'mysql:host=127.0.0.1;port={DBPORT};dbname={DBNAME};charset=utf8mb4')+',"root","");echo json_encode($p->query('+json.dumps(sqltext)+')->fetchAll(PDO::FETCH_ASSOC));'))
def startdb():
 global DBPROC
 DBPROC=subprocess.Popen([str(RUNTIME/'sbin/mariadbd'),'--no-defaults',f'--basedir={RUNTIME}',f'--datadir={ROOT}/db','--socket=',f'--port={DBPORT}','--bind-address=127.0.0.1',f'--pid-file={ROOT}/maria.pid','--user=root','--skip-log-bin'],env=ENV,stdout=DBLOG,stderr=DBLOG)
 for _ in range(100):
  try:
   s=socket.create_connection(('127.0.0.1',DBPORT),.2);s.recv(50);s.close();return
  except OSError:time.sleep(.05)
 raise RuntimeError((ROOT/'maria.log').read_text())
def startweb():
 global WEBPROC
 WEBPROC=subprocess.Popen([PHP,'-S',f'127.0.0.1:{PORT}','-t',str(SITE/'public_html')],env=ENV,stdout=PHPLOG,stderr=PHPLOG)
 for _ in range(100):
  try:urllib.request.urlopen(BASE+'/index.html');return
  except Exception:time.sleep(.03)
 raise RuntimeError('PHP server did not start')
class HostingerTests(unittest.TestCase):
 def setUp(self):
  sql(f'DROP DATABASE IF EXISTS {DBNAME};CREATE DATABASE {DBNAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;',None)
  self.client=self.client_new();self.req('setup',{'username':'admin','password':'AdminPassword123','install_key':KEY})
 def client_new(self):return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
 def req(self,route,data=None,client=None,raw=False,headers=None):
  url=BASE+'/api.php?route='+route
  h={'X-MMI':'1','Content-Type':'application/json'};h.update(headers or {})
  request=urllib.request.Request(url,data=json.dumps(data).encode() if data is not None else None,headers=h)
  with (client or self.client).open(request) as r:return r.read() if raw else json.load(r)
 def visit(self,**kw):
  d=dict(name='Ayesha Ahmed',mobile='03001234567',cnic='0123456789012',host='HR Manager',purpose='Registration',remarks='Documents checked',token='hostinger-visit-token-0001');d.update(kw);return self.req('visit',d)
 def call(self,**kw):
  d=dict(phone='+923001234567',caller='Ayesha Ahmed',at='2026-11-02T12:00:00+05:00',duration=65,spoken_by='Desk',kind='Callback',remarks='Call again',token='hostinger-call-token-0001');d.update(kw);return self.req('call',d)
 def test_01_setup_login_permissions(self):
  self.assertTrue(self.req('status')['loggedIn']);self.assertTrue(self.req('health')['ok'])
  with self.assertRaises(urllib.error.HTTPError):self.req('setup',dict(username='attacker',password='Attacker1234',install_key=KEY))
  self.req('user',dict(username='desk',name='Front Desk',password='DeskPassword123',role='receptionist',active=True));staff=self.client_new();self.req('login',dict(username='desk',password='DeskPassword123'),client=staff)
  for r in ['users','audit','backup','history-backup','database-backup']:
   with self.assertRaises(urllib.error.HTTPError) as e:self.req(r,client=staff)
   self.assertEqual(e.exception.code,403)
  self.req('user',dict(username='desk',name='Front Desk',role='receptionist',active=False))
  with self.assertRaises(urllib.error.HTTPError) as e:self.req('visits',client=staff)
  self.assertEqual(e.exception.code,401)
 def test_02_in_out_repeat_prefix_and_identity(self):
  self.visit();self.visit();self.assertEqual(self.req('visits')['total'],1)
  with self.assertRaises(urllib.error.HTTPError):self.visit(token='hostinger-visit-token-0002')
  for prefix in ['0','03','030','0300']:
   d=self.req('search&q='+prefix+'&mode=phone&paged=1');self.assertEqual(d['total'],1)
  self.req('out',{'id':1});old=self.req('visits')['rows'][0];self.req('out',{'id':1});self.assertEqual(self.req('visits')['rows'][0]['out_at'],old['out_at']);self.assertEqual(old['out_by'],'admin')
  v=self.req('search&q=0300')[0];self.assertEqual(v['last_details']['remarks'],'Documents checked')
  self.visit(visitor_id=v['id'],profile_version=v['version'],token='hostinger-visit-token-0002');self.assertEqual(self.req('visits')['total'],2)
  with self.assertRaises(urllib.error.HTTPError):self.visit(cnic='9999999999999',token='hostinger-visit-token-0003')
 def test_03_corrections_history_snapshots(self):
  self.visit();self.req('out',{'id':1});v=self.req('search&q=0300')[0]
  self.req('profile',dict(id=v['id'],version=v['version'],name='Ayesha Updated',mobile='03009999999',cnic=v['cnic'],reason='Correct spelling'))
  old=self.req('visits')['rows'][0];self.assertEqual(old['name'],'Ayesha Ahmed')
  self.req('edit-visit',dict(id=1,version=old['version'],host='Director',purpose='Updated purpose',remarks='Final note',reason='Reception correction'))
  new=self.req('visits')['rows'][0];self.assertEqual(new['remarks'],'Final note');self.assertEqual(new['updated_by'],'admin');self.assertEqual(old['at'],new['at']);self.assertEqual(old['out_at'],new['out_at'])
  self.assertEqual(len(self.req('changes&entity=visit&id=1')),3)
  with self.assertRaises(urllib.error.HTTPError):self.req('edit-visit',dict(id=1,version=old['version'],reason='Stale correction'))
 def test_04_callbacks_save_match_edit(self):
  self.call();self.call();self.assertEqual(len(self.req('calls')),1)
  found=self.req('caller-search&q=0');self.assertEqual(found['rows'][0]['phone'],'03001234567');self.assertEqual(found['rows'][0]['last_details']['remarks'],'Call again')
  row=self.req('calls')[0];self.call(id=row['id'],version=row['version'],remarks='Updated call',duration=125,reason='Call update') if False else None
  d=dict(id=row['id'],version=row['version'],phone=row['phone'],caller=row['caller'],at=row['at'],duration=125,spoken_by='Desk',kind='Callback',remarks='Updated call',token='hostinger-call-token-0001',reason='Call reviewed')
  self.req('edit-call',d);self.assertEqual(self.req('calls')[0]['duration'],125);self.assertEqual(self.req('calls')[0]['updated_by'],'admin');self.assertEqual(len(self.req('changes&entity=call&id=1')),2)
  with self.assertRaises(urllib.error.HTTPError):self.req('edit-call',d)
 def test_05_excel_backups_and_sql_restore(self):
  self.visit();self.call();self.req('logout',{});self.req('login',dict(username='admin',password='AdminPassword123'))
  from openpyxl import load_workbook
  book=load_workbook(io.BytesIO(self.req('backup',raw=True)),read_only=True,data_only=True);self.assertEqual(book['Visitors']['C2'].value,'03001234567');self.assertEqual(book['Visitors']['D2'].value,'0123456789012');self.assertEqual(book['Visits']['K2'].value,'Documents checked');book.close()
  history=load_workbook(io.BytesIO(self.req('history-backup',raw=True)),read_only=True,data_only=True);self.assertEqual(history['Login Logout History']['F2'].value,'Signed out');history.close()
  self.assertTrue((SITE/'mmi_private/backups/MMI_All_Records.xlsx').is_file());self.assertTrue((SITE/'mmi_private/backups/MMI_Login_Change_History.xlsx').is_file())
  dump=self.req('database-backup',raw=True).decode();sql('CREATE DATABASE IF NOT EXISTS mmi_restore CHARACTER SET utf8mb4;',None);sql(dump,'mmi_restore');self.assertIn('CREATE TABLE',dump)
  restored=phpcode('$p=new PDO('+json.dumps(f'mysql:host=127.0.0.1;port={DBPORT};dbname=mmi_restore')+',"root","");echo json_encode([$p->query("SELECT COUNT(*) FROM visits")->fetchColumn(),$p->query("SELECT COUNT(*) FROM calls")->fetchColumn()]);');self.assertEqual([int(v) for v in json.loads(restored)],[1,1])
 def test_06_security_errors_and_print_escaping(self):
  anonymous=self.client_new()
  with self.assertRaises(urllib.error.HTTPError) as e:self.req('visits',client=anonymous)
  self.assertEqual(e.exception.code,401)
  for h in [{'Host':'attacker.example'},{'Origin':'https://attacker.example'}]:
   with self.assertRaises(urllib.error.HTTPError) as e:self.req('visits',headers=h)
   self.assertEqual(e.exception.code,403)
  self.visit(name='<script>alert(1)</script>');body=self.req('print',raw=True).decode();self.assertIn('&lt;script&gt;',body);self.assertNotIn('<script>alert',body);self.assertIn('Developed by mianmuhamamdtayyab',body)
  with self.assertRaises(urllib.error.HTTPError):self.req('out',{})
  for path in ['/mmi_private/config.php','/mmi/../mmi_private/config.php']:
   with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(BASE.split('/mmi')[0]+path)
 def test_07_restart_persistence(self):
  global WEBPROC,DBPROC
  self.visit();self.call();WEBPROC.terminate();WEBPROC.wait();DBPROC.terminate();DBPROC.wait();startdb();startweb()
  self.assertEqual(self.req('visits')['total'],1);self.assertEqual(len(self.req('calls')),1);self.assertTrue(self.req('status')['loggedIn'])
 def test_08_full_history_505_records(self):
  phpcode('require '+json.dumps(str(SITE/'mmi_private/core.php'))+';require '+json.dumps(str(SITE/'mmi_private/records.php'))+';db()->beginTransaction();for($i=0;$i<505;$i++){execute("INSERT INTO calls(phone,caller,at,duration,remarks,spoken_by,kind,created_at,staff,token) VALUES(?,?,?,?,?,?,?,?,?,?)",["0511234567","Caller ".$i,"2026-11-02T10:00:00+05:00",60,"Discussion","Desk","Incoming","2026-11-02T10:01:00+05:00","admin","bulk-token-".$i]);}db()->commit();')
  data=self.req('calls&paged=1');self.assertEqual(data['total'],505);self.assertEqual(len(data['rows']),30);self.assertEqual(len(self.req('calls&paged=1&page=17')['rows']),25);self.assertEqual(len(self.req('call-export',raw=True).decode('utf-8-sig').splitlines()),506);self.assertIn(b'505 records',self.req('call-print',raw=True))
 def test_09_password_reset_and_throttling(self):
  self.req('user',dict(username='desk',name='Desk',password='DeskPassword123',role='receptionist',active=True));staff=self.client_new();self.req('login',dict(username='desk',password='DeskPassword123'),client=staff)
  self.req('user',dict(username='desk',name='Desk',password='NewDeskPassword123',role='receptionist',active=True))
  with self.assertRaises(urllib.error.HTTPError):self.req('visits',client=staff)
  for _ in range(8):
   with self.assertRaises(urllib.error.HTTPError):self.req('login',dict(username='wrong',password='WrongPassword123'))
  with self.assertRaises(urllib.error.HTTPError) as e:self.req('login',dict(username='wrong',password='WrongPassword123'))
  self.assertEqual(e.exception.code,429)
 def test_10_browser(self):
  script=Path(__file__).with_name('browser_workflow.cjs')
  if os.environ.get('MMI_TEST_BROWSER')!='1':self.skipTest('Set MMI_TEST_BROWSER=1 to enable Playwright browser checks')
  env=ENV.copy();env['MMI_TEST_URL']=BASE;env['MMI_TEST_INSTALL_KEY']=KEY
  r=subprocess.run(['node',str(script)],env=env,capture_output=True,text=True,timeout=120)
  self.assertEqual(r.returncode,0,r.stdout+r.stderr);print(r.stdout.strip())

 def test_11_browser_first_admin_and_preflight(self):
  sql(f'DROP DATABASE {DBNAME};CREATE DATABASE {DBNAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;',None)
  with urllib.request.urlopen(BASE+'/install.php') as response:self.assertIn(b'Installation',response.read())
  self.test_10_browser()
 def test_12_desktop_records_migration(self):
  source=ROOT/'desktop.sqlite3';dest=ROOT/'desktop-import.sql'
  with sqlite3.connect(source) as c:
   c.executescript("CREATE TABLE visitors(id INTEGER PRIMARY KEY,name TEXT,mobile TEXT,cnic TEXT);CREATE TABLE visits(id INTEGER PRIMARY KEY,visitor_id INTEGER,at TEXT,purpose TEXT,token TEXT);")
   c.execute('INSERT INTO visitors VALUES(1,?,?,?)',('Migrated Visitor','03001111111','1234512345671'));c.execute('INSERT INTO visits VALUES(1,1,?,?,?)',('2026-11-01T10:00:00+05:00','Imported notes','old-desktop-token-0001'))
  r=subprocess.run([sys.executable,str(SRC/'tools/export_desktop_records.py'),str(source),str(dest)],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr);sql(dest.read_text())
  found=self.req('search&q=03001111111')[0];self.assertEqual(found['name'],'Migrated Visitor');self.assertEqual(self.req('visits')['total'],1)
  self.visit(name=found['name'],mobile=found['mobile'],cnic=found['cnic'],visitor_id=found['id'],profile_version=found['version']);self.assertEqual(self.req('visits')['total'],2)

 def test_13_concurrent_duplicate_requests(self):
  from concurrent.futures import ThreadPoolExecutor
  code='require '+json.dumps(str(SITE/'mmi_private/core.php'))+';require '+json.dumps(str(SITE/'mmi_private/records.php'))+';$d=json_decode('+json.dumps(json.dumps(dict(name='Parallel Visitor',mobile='03001111111',cnic='1234512345671',host='HR',purpose='Concurrent check',remarks='One record',token='parallel-php-token-0001')))+',true);echo json_encode(save_visit($d,["id"=>1,"username"=>"admin","role"=>"admin"]));'
  with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(lambda _:json.loads(phpcode(code)),range(12)))
  self.assertEqual({int(r['id']) for r in results},{1});self.assertEqual(self.req('visits')['total'],1)
 def test_14_excel_failure_preserves_database(self):
  folder=SITE/'mmi_private/backups';held=SITE/'mmi_private/backups-held';folder.rename(held);folder.write_text('Simulated unavailable directory')
  try:
   result=self.visit();self.assertIn('backup_warning',result);self.assertEqual(self.req('visits')['total'],1)
  finally:folder.unlink();held.rename(folder)
  self.assertTrue(self.req('backup',raw=True).startswith(b'PK'))
 def test_15_request_validation_and_sql_injection(self):
  self.assertEqual(self.req('search&q=%27%20OR%201%3D1%20--'),[])
  request=urllib.request.Request(BASE+'/api.php?route=visit',data=b'{}',headers={'Content-Type':'application/json'})
  with self.assertRaises(urllib.error.HTTPError) as e:self.client.open(request)
  self.assertEqual(e.exception.code,403)
  with self.assertRaises(urllib.error.HTTPError) as e:self.req('call',dict(phone='1',caller='Invalid'))
  self.assertEqual(e.exception.code,400)

try:
 init=subprocess.run([str(RUNTIME/'bin/mariadb-install-db'),'--no-defaults',f'--basedir={RUNTIME}',f'--datadir={ROOT}/db','--auth-root-authentication-method=normal','--skip-test-db','--user=root'],env=ENV,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 if init.returncode:raise RuntimeError(init.stdout.decode()+init.stderr.decode())
 startdb();startweb();result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(HostingerTests));(Path('/tmp/mmi-php-test-result.json')).write_text(json.dumps({'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),'root':str(ROOT)}));
 if not result.wasSuccessful():print('PHP LOG TAIL:',(ROOT/'php.log').read_text()[-7000:])
 sys.exit(0 if result.wasSuccessful() else 1)
finally:
 for p in [WEBPROC,DBPROC]:
  if p and p.poll() is None:p.terminate();p.wait()
 TEMP.cleanup()
