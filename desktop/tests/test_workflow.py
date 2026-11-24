import unittest,tempfile,threading,urllib.request,urllib.error,json,http.cookiejar,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));import app
class Workflow(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();app.DATA=Path(self.tmp.name);app.SESSIONS.clear();app.ATTEMPTS.clear();app.init();self.s=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler);threading.Thread(target=self.s.serve_forever,daemon=True).start();self.base='http://127.0.0.1:'+str(self.s.server_port);self.admin=self.client();self.staff=self.client()
 def client(self):return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
 def req(self,client,path,data=None):
  r=client.open(urllib.request.Request(self.base+path,data=json.dumps(data).encode() if data is not None else None,headers={'X-MMI':'1','Content-Type':'application/json'}));return json.load(r)
 def tearDown(self):self.s.shutdown();self.s.server_close();self.tmp.cleanup()
 def test_full_reception_workflow(self):
  self.req(self.admin,'/api/setup',dict(username='admin',password='AdminPass1234'))
  self.req(self.admin,'/api/user',dict(username='reception',name='Reception One',role='receptionist',password='Reception123',active=True))
  self.req(self.staff,'/api/login',dict(username='reception',password='Reception123'))
  self.assertTrue(self.req(self.staff,'/api/health')['ok'])
  with self.assertRaises(urllib.error.HTTPError) as e:self.req(self.staff,'/api/users')
  self.assertEqual(e.exception.code,403)
  d=dict(name='Visitor One',mobile='03001234567',cnic='1234512345671',host='Manager',purpose='Meeting',token='workflow-token-00001')
  visit=self.req(self.staff,'/api/visit',d);self.req(self.staff,'/api/visit',d)
  d['token']='workflow-token-00002'
  with self.assertRaises(urllib.error.HTTPError):self.req(self.staff,'/api/visit',d)
  self.assertEqual(self.req(self.staff,'/api/visits')['stats']['inside'],1)
  self.req(self.staff,'/api/out',{'id':visit['id']});first=self.req(self.staff,'/api/visits')['rows'][0]['out_at'];self.req(self.staff,'/api/out',{'id':visit['id']})
  self.assertEqual(first,self.req(self.staff,'/api/visits')['rows'][0]['out_at'])
  self.req(self.staff,'/api/visit',d)
  self.assertEqual(len(self.req(self.staff,'/api/search?q=03001234567')),1)
  c=dict(phone='0511234567',caller='Caller',at='2026-11-02T12:30:00+05:00',duration=123,spoken_by='Reception One',kind='Callback',remarks='Follow up',token='call-token-000000001')
  self.req(self.staff,'/api/call',c);self.req(self.staff,'/api/call',c)
  self.assertEqual(len(self.req(self.staff,'/api/calls')),1)
  self.assertEqual(self.req(self.staff,'/api/calls')[0]['duration'],123)
  self.req(self.staff,'/api/logout',{});audit=self.req(self.admin,'/api/audit');self.assertTrue(any(r['logout_at'] for r in audit))
  self.req(self.staff,'/api/login',dict(username='reception',password='Reception123'))
  self.req(self.admin,'/api/user',dict(username='reception',name='Reception One',role='receptionist',active=False))
  with self.assertRaises(urllib.error.HTTPError) as e:self.req(self.staff,'/api/visits')
  self.assertEqual(e.exception.code,401)
 def test_upgrade_requires_previous_password(self):
  with app.db() as c:
   salt='ab'*16;c.execute("INSERT INTO settings VALUES('auth',?)",(json.dumps([salt,app.password('Previous1234',salt)]),))
  with self.assertRaises(urllib.error.HTTPError):self.req(self.admin,'/api/setup',dict(username='admin',password='AdminPass1234'))
  self.req(self.admin,'/api/setup',dict(username='admin',password='AdminPass1234',old_password='Previous1234'))
if __name__=='__main__':unittest.main()
