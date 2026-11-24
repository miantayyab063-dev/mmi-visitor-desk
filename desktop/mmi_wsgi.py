"""WSGI adapter: local desktop and website use the same handlers/database."""
import io
from email.message import Message
from http import HTTPStatus
from urllib.parse import quote
import app

class WSGIHandler(app.Handler):
    def __init__(self,environ):
        self.command=environ.get('REQUEST_METHOD','GET')
        self.path=quote(environ.get('PATH_INFO','/'),safe='/')
        if environ.get('QUERY_STRING'):self.path+='?'+environ['QUERY_STRING']
        self.client_address=(environ.get('REMOTE_ADDR','127.0.0.1'),0)
        self.headers=Message()
        for key,value in environ.items():
            if key.startswith('HTTP_'):self.headers[key[5:].replace('_','-')]=value
        for key in ('CONTENT_LENGTH','CONTENT_TYPE'):
            if environ.get(key):self.headers[key.replace('_','-')]=environ[key]
        self.rfile=environ['wsgi.input'];self.wfile=io.BytesIO();self.response_headers=[];self.response_status=500
    def send_response(self,code,message=None):self.response_status=code
    def send_header(self,key,value):self.response_headers.append((key,str(value)))
    def end_headers(self):pass

def application(environ,start_response):
    handler=WSGIHandler(environ)
    if handler.command=='GET':handler.do_GET()
    elif handler.command=='POST':handler.do_POST()
    else:handler.send(405,{'error':'Method not allowed.'},extra={'Allow':'GET, POST'})
    start_response(str(handler.response_status)+' '+HTTPStatus(handler.response_status).phrase,handler.response_headers)
    return [handler.wfile.getvalue()]
