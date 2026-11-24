import unittest,sys,urllib.request,urllib.error,sqlite3,io,json,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));import app,mmi_wsgi
import test_reliability as helpers
class FeaturesSecurity(unittest.TestCase):
 setUp=helpers.Reliability.setUp
 tearDown=helpers.Reliability.tearDown
 start=helpers.Reliability.start
 stop=helpers.Reliability.stop
 request=helpers.Reliability.request
 visit=helpers.Reliability.visit
 def new_visit(self):return self.request('/api/visit',self.visit())
 def test_prefix_lookup_and_all_pages(self):
  with app.db() as c:
   for i in range(65):c.execute('INSERT INTO visitors(name,mobile,cnic) VALUES(?,?,?)',(f'Prefix Person {i}',f'030{i:08}',f'{i:013}'))
   c.execute('INSERT INTO visitors(name,mobile,cnic) VALUES(?,?,?)',('Other Operator','03111234567','8888888888888'))
  r=self.request('/api/search?q=0&mode=phone&paged=1');self.assertEqual(r['total'],66);self.assertEqual(len(r['rows']),30)
  r=self.request('/api/search?q=03&mode=phone&paged=1');self.assertEqual(r['total'],66)
  r=self.request('/api/search?q=030&mode=phone&paged=1');self.assertEqual(r['total'],65);self.assertTrue(all(v['mobile'].startswith('030') for v in r['rows']))
  r=self.request('/api/search?q=030&mode=phone&paged=1&page=3');self.assertEqual(len(r['rows']),5)
  self.assertEqual(self.request('/api/search?q=9&mode=phone&paged=1')['total'],0)
 def test_profile_and_visit_changes_preserve_originals(self):
  self.new_visit();v=self.request('/api/search?q=0300&mode=phone')[0]
  self.request('/api/out',{'id':1})
  self.request('/api/profile',dict(id=v['id'],version=v['version'],name='Corrected Name',mobile='03009999999',cnic=v['cnic'],reason='Typo correction'))
  old=self.request('/api/visits')['rows'][0];self.assertEqual(old['name'],'Durable Visitor');self.assertEqual(old['mobile'],'03001234567')
  corrected=self.request('/api/search?q=03009999999&mode=phone')[0]
  self.assertEqual(corrected['name'],'Corrected Name');self.assertEqual(corrected['last_details']['host'],'Director')
  self.request('/api/visit',dict(visitor_id=corrected['id'],profile_version=corrected['version'],name=corrected['name'],mobile=corrected['mobile'],cnic=corrected['cnic'],host='HR',purpose='New meeting',remarks='Follow up',token='followup-record-0001'))
  self.assertEqual(self.request('/api/visits?visitor=1')['total'],2)
  self.assertEqual(self.request('/api/visits?q=03001234567')['total'],2)
  self.request('/api/edit-visit',dict(id=old['id'],version=old['version'],host='Finance',purpose='Correction',remarks='Final remarks',reason='Reception correction'))
  changed=[r for r in self.request('/api/visits')['rows'] if r['id']==1][0]
  self.assertEqual(changed['at'],old['at']);self.assertEqual(changed['out_at'],old['out_at']);self.assertEqual(changed['remarks'],'Final remarks');self.assertEqual(changed['updated_by'],'admin')
  with self.assertRaises(urllib.error.HTTPError):self.request('/api/edit-visit',dict(id=1,version=old['version'],reason='stale data',host='x'))
  changes=self.request('/api/changes?entity=visit&id=1');self.assertEqual(len(changes),3)
  self.assertTrue((app.DATA/'backups'/'MMI_Login_Change_History.xlsx').is_file())
 def test_print_is_complete_and_escaped(self):
  d=self.visit();d['name']='<script>alert(1)</script>';self.request('/api/visit',d)
  text=self.request('/api/print?q=0300',raw=True).decode();self.assertIn('&lt;script&gt;',text);self.assertNotIn('<script>alert',text);self.assertIn('admin',text);self.assertIn('Director',text)
  self.assertIn(b'Visit ID',self.request('/api/export',raw=True))
 def test_origin_host_and_backups_access(self):
  for headers in [{'Host':'attacker.example'},{'Origin':'https://attacker.example'}]:
   with self.assertRaises(urllib.error.HTTPError) as e:self.client.open(urllib.request.Request(self.base+'/api/visits',headers=headers))
   self.assertEqual(e.exception.code,403)
  self.request('/api/user',dict(username='desk',name='Desk',password='DeskPassword123',role='receptionist',active=True))
  self.request('/api/logout',{});self.request('/api/login',dict(username='desk',password='DeskPassword123'))
  for path in ['/api/database-backup','/api/backup','/api/history-backup','/api/users','/api/audit']:
   with self.assertRaises(urllib.error.HTTPError) as e:self.request(path)
   self.assertEqual(e.exception.code,403)
  with self.assertRaises(urllib.error.HTTPError):self.request('/data/mmi.sqlite3',raw=True)
 def test_audit_append_only_and_logout_saved(self):
  self.new_visit()
  with app.db() as c:
   with self.assertRaises(sqlite3.IntegrityError):c.execute('DELETE FROM change_log')
  self.request('/api/logout',{})
  with app.db() as c:
   row=c.execute('SELECT * FROM sessions_log ORDER BY id DESC').fetchone();self.assertTrue(row['logout_at']);self.assertEqual(row['end_reason'],'Signed out')
  self.request('/api/login',dict(username='admin',password='TestAdmin123'));self.assertTrue(self.request('/api/status')['user']['previous_login']['logout_at'])
 def test_call_edit_and_change_history(self):
  d=dict(phone='0511234567',caller='Caller',at='2026-11-02T10:00:00+05:00',duration=60,remarks='First note',spoken_by='Desk',kind='Incoming',token='call-update-test-0001')
  self.request('/api/call',d);row=self.request('/api/calls')[0];d.update(id=row['id'],version=row['version'],remarks='Corrected note',duration=90,reason='Duration correction')
  self.request('/api/edit-call',d);changed=self.request('/api/calls')[0];self.assertEqual(changed['duration'],90);self.assertEqual(changed['updated_by'],'admin');self.assertEqual(changed['staff'],'admin')
  self.assertEqual(len(self.request('/api/changes?entity=call&id=1')),2)
  with self.assertRaises(urllib.error.HTTPError):self.request('/api/edit-call',d)
 def test_wsgi_same_database(self):
  cookies='; '.join(c.name+'='+c.value for h in self.client.handlers if hasattr(h,'cookiejar') for c in h.cookiejar)
  env={'REQUEST_METHOD':'GET','PATH_INFO':'/api/health','QUERY_STRING':'','REMOTE_ADDR':'127.0.0.1','HTTP_HOST':'127.0.0.1:8765','HTTP_COOKIE':cookies,'wsgi.input':io.BytesIO(b'')}
  status=[];out=mmi_wsgi.application(env,lambda code,headers:status.append(code));self.assertEqual(status[0],'200 OK');self.assertTrue(json.loads(b''.join(out))['ok'])
  env['PATH_INFO']='/api/visits';out=mmi_wsgi.application(env,lambda code,headers:None);self.assertEqual(json.loads(b''.join(out))['total'],0)
if __name__=='__main__':unittest.main()
