import unittest,tempfile,sys,io,zipfile,xml.etree.ElementTree as ET
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));import app,excel_backup
class ExcelBackup(unittest.TestCase):
 def test_all_records_and_identifiers(self):
  with tempfile.TemporaryDirectory() as tmp:
   app.DATA=Path(tmp);app.init()
   with app.db() as c:
    c.execute("INSERT INTO visitors(name,mobile,cnic) VALUES(?,?,?)",('=Not a formula','03001234567','0123456789012'))
    for i in range(505):
     c.execute('INSERT INTO visits(visitor_id,at,purpose,token) VALUES(1,?,?,?)',('2026-11-02T10:00:00+05:00','A & B',str(i)))
     c.execute('INSERT INTO calls(phone,caller,at,duration,remarks,spoken_by,kind,created_at,staff,token) VALUES(?,?,?,?,?,?,?,?,?,?)',('0511234567','Caller','2026-11-02T10:00:00+05:00',10,'Discussion','Reception','Callback','2026-11-02T10:01:00+05:00','staff',str(i)))
   with app.db() as c:raw=excel_backup.export(c)
   ns={'x':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
   with zipfile.ZipFile(io.BytesIO(raw)) as z:
    self.assertIsNone(z.testzip())
    for n in [2,3]:self.assertEqual(len(ET.fromstring(z.read(f'xl/worksheets/sheet{n}.xml')).findall('x:sheetData/x:row',ns)),506)
    p=ET.fromstring(z.read('xl/worksheets/sheet1.xml'));self.assertEqual(p.find(".//x:c[@r='C2']/x:is/x:t",ns).text,'03001234567');self.assertEqual(p.find(".//x:c[@r='D2']/x:is/x:t",ns).text,'0123456789012');self.assertFalse(p.findall('.//x:f',ns))
if __name__=='__main__':unittest.main()
