import unittest,tempfile,sys,threading,concurrent.futures,sqlite3,zipfile,io,json,urllib.request,urllib.error,http.cookiejar,xml.etree.ElementTree as ET
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));import app
class Reliability(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();app.DATA=Path(self.tmp.name);app.init();app.SESSIONS.clear();app.ATTEMPTS.clear();self.start()
  self.client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
  self.request('/api/setup',dict(username='admin',password='TestAdmin123'))
 def start(self):
  self.server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.base='http://127.0.0.1:'+str(self.server.server_port)
 def stop(self):self.server.shutdown();self.server.server_close();self.thread.join()
 def tearDown(self):self.stop();self.tmp.cleanup()
 def request(self,path,data=None,raw=False):
  r=self.client.open(urllib.request.Request(self.base+path,data=None if data is None else json.dumps(data).encode(),headers={'X-MMI':'1','Content-Type':'application/json'}));return r.read() if raw else json.load(r)
 def visit(self):return dict(name='Durable Visitor',mobile='03001234567',cnic='0123456789012',host='Director',purpose='Documents',token='durability-test-0001')
 def test_disk_excel_restart_and_restore(self):
  self.request('/api/visit',self.visit());self.request('/api/out',{'id':1})
  self.request('/api/call',dict(phone='0511234567',caller='Caller',at='2026-11-02T12:30:00+05:00',duration=300,spoken_by='Desk',kind='Incoming',remarks='Callback required',token='durability-call-0001'))
  file=app.DATA/'backups'/'MMI_All_Records.xlsx';self.assertTrue(file.is_file())
  ns={'x':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
  with zipfile.ZipFile(file) as z:
   rows=ET.fromstring(z.read('xl/worksheets/sheet2.xml'));texts=[e.text for e in rows.findall('.//x:t',ns)];self.assertIn('Durable Visitor',texts);self.assertIn('0123456789012',texts);self.assertIn('Director',texts);self.assertEqual(len(rows.findall('x:sheetData/x:row',ns)),2)
   calls=ET.fromstring(z.read('xl/worksheets/sheet3.xml'));self.assertIn('Callback required',[e.text for e in calls.findall('.//x:t',ns)])
  backup=self.request('/api/database-backup',raw=True);dest=app.DATA/'restored.sqlite3';dest.write_bytes(backup)
  with sqlite3.connect(dest) as c:
   self.assertEqual(c.execute('PRAGMA integrity_check').fetchone()[0],'ok');self.assertEqual(c.execute('SELECT COUNT(*) FROM visits WHERE out_at IS NOT NULL').fetchone()[0],1)
  self.stop();app.SESSIONS.clear();app.init();self.start()
  self.request('/api/login',dict(username='admin',password='TestAdmin123'))
  self.assertEqual(self.request('/api/visits')['total'],1);self.assertEqual(len(self.request('/api/calls')),1)
 def test_concurrent_double_submit(self):
  d=self.visit();d['_staff']='admin'
  with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(lambda _:app.record(d),range(12)))
  self.assertEqual({r['id'] for r in results},{1})
  with app.db() as c:self.assertEqual(c.execute('SELECT count(*) FROM visits').fetchone()[0],1);self.assertEqual(c.execute('PRAGMA integrity_check').fetchone()[0],'ok')
 def test_backup_failure_does_not_lose_database_record(self):
  import unittest.mock
  with unittest.mock.patch.object(app.excel_backup,'export',side_effect=OSError('disk failure')):
   r=self.request('/api/visit',self.visit());self.assertIn('backup_warning',r)
  self.assertEqual(self.request('/api/visits')['total'],1)
  self.assertTrue(self.request('/api/backup',raw=True).startswith(b'PK'))
 def test_bad_requests_and_expired_session(self):
  for path,data in [('/api/out',{}),('/api/call',[]),('/api/visit',None)]:
   if data is None:data={}
   with self.assertRaises(urllib.error.HTTPError) as e:self.request(path,data)
   self.assertEqual(e.exception.code,400)
  with self.assertRaises(urllib.error.HTTPError) as e:self.request('/api/visits?page=abc')
  self.assertEqual(e.exception.code,400)
  self.assertTrue(self.request('/api/health')['ok'])
  for session in app.SESSIONS.values():session['expires']=0
  with self.assertRaises(urllib.error.HTTPError) as e:self.request('/api/visits')
  self.assertEqual(e.exception.code,401)
