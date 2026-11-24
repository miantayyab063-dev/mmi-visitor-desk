"""Production website entry point, behind an HTTPS reverse proxy."""
import os
from urllib.parse import urlsplit
import app

def main():
    origin=os.environ.get('MMI_PUBLIC_ORIGIN','').rstrip('/')
    parsed=urlsplit(origin)
    if parsed.scheme!='https' or not parsed.hostname or parsed.path or parsed.query or parsed.fragment:
        raise SystemExit('Set MMI_PUBLIC_ORIGIN=https://your-domain.example (no path).')
    os.environ['MMI_ALLOWED_HOSTS']=parsed.hostname
    os.environ['MMI_SECURE_COOKIE']='1'
    os.environ['MMI_SETUP_DISABLED']='1'
    app.init()
    with app.db() as c:
        if not c.execute("SELECT 1 FROM users WHERE role='admin' AND active=1").fetchone():
            raise SystemExit('Initialize admin locally first: set the same MMI_DATA_DIR and run python app.py. Then stop it and start this website entry point.')
    try:app.refresh_backups()
    except OSError:print('Warning: Excel backup cannot be refreshed; check disk permissions.')
    from waitress import serve
    from mmi_wsgi import application
    print('MMI website backend: 127.0.0.1:8765. Use HTTPS reverse proxy. One process only.')
    serve(application,listen='127.0.0.1:8765',threads=8,max_request_body_size=8192,
          trusted_proxy='127.0.0.1',trusted_proxy_headers={'x-forwarded-for','x-forwarded-proto'},
          clear_untrusted_proxy_headers=True,url_scheme='https',ident='MMI')
if __name__=='__main__':main()
