import os

os.environ["DATA_DIR"] = "/tmp/site-delivery-test-data"
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "test-password"

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
import app as service

# Share the same in-memory database among request threads.
service.engine.dispose()
service.engine = service.create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
service.event.listen(service.engine, "connect", service.sqlite_setup)
service.SessionLocal.configure(bind=service.engine)

def test_owner_transfer_progress_and_conflict():
    with TestClient(service.app) as admin, TestClient(service.app) as alice, TestClient(service.app) as bob:
        assert admin.post('/api/v1/auth/login', json={'username':'admin','password':'test-password'}).status_code == 200
        a = admin.post('/api/v1/users', json={'username':'alice','password':'password','name':'Alice'}).json()['id']
        b = admin.post('/api/v1/users', json={'username':'bob','password':'password','name':'Bob'}).json()['id']
        assert alice.post('/api/v1/auth/login', json={'username':'alice','password':'password'}).status_code == 200
        assert bob.post('/api/v1/auth/login', json={'username':'bob','password':'password'}).status_code == 200
        payload = {'name':'测试局点','owner_id':a}
        site = alice.post('/api/v1/sites', json=payload).json()
        url = '/api/v1/sites/' + site['id']
        assert bob.post(url+'/progress', json={'content':'无权','occurred_at':'2026-11-10T00:00:00Z'}).status_code == 403
        assert alice.post(url+'/progress', json={'content':'较新','occurred_at':'2026-11-10T00:00:00Z','todos':[{'content':'跟进'}]}).status_code == 201
        assert alice.post(url+'/progress', json={'content':'补录旧进展','occurred_at':'2026-11-01T00:00:00Z'}).status_code == 201
        assert alice.get(url).json()['latest_progress']['content'] == '较新'
        todo = alice.get(url+'/todos').json()[0]
        transfer = alice.put(url, json={**payload, 'owner_id': b, 'version': 1})
        assert transfer.status_code == 200
        assert alice.post('/api/v1/todos/'+todo['id']+'/complete').status_code == 403
        assert bob.post('/api/v1/todos/'+todo['id']+'/complete').status_code == 200
        assert bob.put(url, json={**payload, 'owner_id': b, 'version': 1}).status_code == 409
        assert alice.post(url+'/contacts', json={'name':'客户'}).status_code == 403
        assert bob.post(url+'/contacts', json={'name':'客户','employee_no':'123'}).status_code == 201
        assert alice.get(url+'/contacts').json()[0]['employee_no'] == '123'
        upload = bob.post(url+'/attachments', files={'file':('test.txt', b'hello', 'text/plain')})
        assert upload.status_code == 201
        assert alice.get('/api/v1/attachments/'+upload.json()['id']+'/download').content == b'hello'
        tag = bob.post('/api/v1/tags', json={'name':'2026重点'}).json()
        assert alice.post(url+'/tags/'+tag['id']).status_code == 403
        assert bob.post(url+'/tags/'+tag['id']).status_code == 200
        assert bob.get(url).json()['tags'][0]['name'] == '2026重点'
        latest = bob.get(url+'/progress').json()[0]
        assert bob.post('/api/v1/progress/'+latest['id']+'/void').status_code == 200
        assert bob.get(url).json()['latest_progress']['content'] == '补录旧进展'
