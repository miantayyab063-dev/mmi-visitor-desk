import unittest,sys,urllib.error,zipfile,io
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));import app
import test_reliability as helpers
class CallbacksComplete(unittest.TestCase):
 setUp=helpers.Reliability.setUp
 tearDown=helpers.Reliability.tearDown
 start=helpers.Reliability.start
 stop=helpers.Reliability.stop
 request=helpers.Reliability.request
 visit=helpers.Reliability.visit
 def test_saved_caller_autofill_and_prefix(self):
  self.request('/api/visit',self.visit())
  self.request('/api/call',dict(phone='+923001234567',caller='Caller <one>',at='2026-11-02T10:00:00+05:00',duration=31,remarks='Follow up today',spoken_by='Desk',kind='Callback',token='callback-complete-0001'))
  found=self.request('/api/caller-search?q=0');self.assertEqual(found['total'],1);self.assertEqual(found['rows'][0]['phone'],'03001234567');self.assertEqual(found['rows'][0]['last_details']['remarks'],'Follow up today')
  self.assertEqual(self.request('/api/caller-search?q=031')['total'],0)
  self.assertEqual(self.request('/api/caller-search?q=Caller&mode=name')['total'],1)
  self.assertIn(b'Caller &lt;one&gt;',self.request('/api/call-print',raw=True));self.assertIn(b'Developed by mianmuhamamdtayyab',self.request('/api/call-print',raw=True))
 def test_full_history_pagination_search_export(self):
  with app.db() as c:
   for i in range(505):c.execute('INSERT INTO calls(phone,caller,at,duration,remarks,spoken_by,kind,created_at,staff,token) VALUES(?,?,?,?,?,?,?,?,?,?)',('0511234567',f'Caller {i}','2026-11-02T10:00:00+05:00',60,'Discussed','Desk','Incoming','2026-11-02T10:01:00+05:00','admin',f'callback-bulk-{i}'))
  data=self.request('/api/calls?paged=1');self.assertEqual(data['total'],505);self.assertEqual(len(data['rows']),30)
  self.assertEqual(len(self.request('/api/calls?paged=1&page=17')['rows']),25)
  self.assertEqual(self.request('/api/calls?paged=1&q=Caller%200')['total'],1)
  self.assertEqual(self.request('/api/calls?paged=1&date=2026-11-01')['total'],0)
  self.assertEqual(len(self.request('/api/call-export',raw=True).decode('utf-8-sig').splitlines()),506)
  self.assertIn(b'505 records',self.request('/api/call-print',raw=True))
 def test_all_assets_connected_and_branded(self):
  text=self.request('/',raw=True).decode();self.assertIn('Developed by',text);self.assertIn('mianmuhamamdtayyab',text)
  for path in ['/app.js','/style.css','/print.js']:self.assertTrue(self.request(path,raw=True))
  from html.parser import HTMLParser
  class IDs(HTMLParser):
   def __init__(self):super().__init__();self.ids=[]
   def handle_starttag(self,tag,attrs):
    for k,v in attrs:
     if k=='id':self.ids.append(v)
  parser=IDs();parser.feed(text);self.assertEqual(len(parser.ids),len(set(parser.ids)))
  import re
  js=(app.ROOT/'static'/'app.js').read_text()
  for id in re.findall(r"\$\([\"']([^\"']+)[\"']\)",js):self.assertIn(id,parser.ids)
if __name__=='__main__':unittest.main()
