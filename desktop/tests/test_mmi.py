import unittest,tempfile,sys,sqlite3
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
class Register(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();app.DATA=Path(self.tmp.name);app.init()
 def tearDown(self):self.tmp.cleanup()
 def entry(self,**kw):
  d=dict(name='Test Visitor',mobile='03001234567',cnic='12345-1234567-1',token='a'*24);d.update(kw);return app.record(d)
 def test_return_visit_and_retry(self):
  self.entry();self.entry();self.entry(token='b'*24,mobile='+923001234567')
  with app.db() as c:
   self.assertEqual(c.execute('select count(*) from visitors').fetchone()[0],1);self.assertEqual(c.execute('select count(*) from visits').fetchone()[0],2)
   self.assertTrue(c.execute('select at from visits').fetchone()[0].endswith('+05:00'))
 def test_conflict_rollback(self):
  self.entry()
  with self.assertRaises(ValueError):self.entry(cnic='9999999999999',token='b'*24)
  with app.db() as c:self.assertEqual(c.execute('select count(*) from visits').fetchone()[0],1)
 def test_invalid(self):
  for kw in [dict(mobile='123'),dict(cnic='123'),dict(name=''),dict(token='')]:
   with self.assertRaises(ValueError):self.entry(**kw)
 def test_persistence(self):
  self.entry();app.init()
  with app.db() as c:self.assertEqual(c.execute('select name from visitors').fetchone()[0],'Test Visitor')
if __name__=='__main__':unittest.main()
