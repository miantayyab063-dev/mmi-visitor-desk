"""Export desktop MMI records to MySQL SQL. Run on a stopped/backed-up desktop database.
Import ONLY into a fresh, installed MMI website with no visitor/call records.
Does not migrate passwords/accounts; create corresponding website staff accounts separately.
"""
import argparse,sqlite3,json,hashlib
from pathlib import Path

def literal(v):
    if v is None:return 'NULL'
    if isinstance(v,(int,float)):return str(v)
    raw=str(v).encode('utf-8').hex()
    return "CONVERT(0x"+raw+" USING utf8mb4)" if raw else "''"
def insert(table,row):
    return 'INSERT INTO `'+table+'` ('+','.join('`'+k+'`' for k in row)+') VALUES ('+','.join(literal(v) for v in row.values())+');'
def convert(source,destination):
    uri=source.resolve().as_uri()+'?mode=ro';db=sqlite3.connect(uri,uri=True);db.row_factory=sqlite3.Row
    out=['-- MMI desktop records import. Fresh website with ZERO visitors/calls only.','-- Login accounts/passwords are not migrated. Create staff accounts in the website.','SET NAMES utf8mb4;','START TRANSACTION;']
    names={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    people={r['id']:dict(r) for r in db.execute('SELECT * FROM visitors')}
    for row in people.values():out.append(insert('visitors',{k:row.get(k,1 if k=='version' else '') for k in ['id','name','mobile','cnic','version']}))
    if 'visits' in names:
        for item in db.execute('SELECT * FROM visits ORDER BY id'):
            r=dict(item);v=people[r['visitor_id']]
            for k in ['name','mobile','cnic']:r.setdefault('snapshot_'+k,v[k])
            for k in ['host','remarks','out_by','updated_by','staff']:r.setdefault(k,'')
            for k in ['out_at','updated_at']:r.setdefault(k,None)
            r.setdefault('version',1)
            out.append(insert('visits',{k:r[k] for k in ['id','visitor_id','at','out_at','host','purpose','remarks','staff','out_by','updated_at','updated_by','version','snapshot_name','snapshot_mobile','snapshot_cnic','token']}))
    if 'calls' in names:
        for item in db.execute('SELECT * FROM calls ORDER BY id'):
            r=dict(item);r.setdefault('version',1);r.setdefault('updated_at',None);r.setdefault('updated_by','')
            p=r['phone']
            if p.startswith('0092') and len(p)==14:r['phone']='0'+p[4:]
            elif p.startswith('92') and len(p)==12:r['phone']='0'+p[2:]
            out.append(insert('calls',{k:r[k] for k in ['id','phone','caller','at','duration','remarks','spoken_by','kind','created_at','staff','token','version','updated_at','updated_by']}))
    if 'change_log' in names:
        for item in db.execute('SELECT * FROM change_log ORDER BY id'):
            r=dict(item);r.pop('id',None);out.append(insert('change_log',r))
    if 'sessions_log' in names:
        for item in db.execute('SELECT * FROM sessions_log ORDER BY id'):
            r=dict(item);original_id=r['id'];r.pop('id',None)
            r.update(user_id=0,token_hash=hashlib.sha256(('desktop-import-'+str(source.resolve())+'-'+str(original_id)).encode()).hexdigest(),auth_version=0,expires=0,activity=0)
            r.setdefault('last_seen',r.get('login_at'));r['end_reason']=r.get('end_reason') or 'Imported desktop history; session not active'
            out.append(insert('sessions_log',r))
    out+=['COMMIT;','-- Verify record counts in MMI, then download fresh Excel and MySQL backups.']
    destination.write_text('\n'.join(out)+'\n',encoding='utf-8');db.close();return len(people)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if not a.source.is_file():p.error('Desktop database not found.')
    if a.output.exists():p.error('Choose a new output filename; existing files are not overwritten.')
    print('Visitor profiles exported:',convert(a.source,a.output));print('SQL file:',a.output)
