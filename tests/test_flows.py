import importlib.util
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import config
BOOT = tempfile.TemporaryDirectory()
with patch.object(config, 'DATABASE', Path(BOOT.name)/'boot.db'), patch.object(config, 'UPLOAD_FOLDER', Path(BOOT.name)/'uploads'):
    spec = importlib.util.spec_from_file_location('tested_app', ROOT/'app.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

class SecurityFlows(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.database = Path(self.tmp.name)/'test.db'
        self.patch = patch.object(module, 'DATABASE', self.database)
        self.patch.start()
        module.app.config.update(TESTING=True)
        module.init_db()
        self.client = module.app.test_client()
        self.runner = module.app.test_cli_runner()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def post(self, path, fields=None):
        with self.client.session_transaction() as s:
            token = s.setdefault('csrf', 'test-token')
        return self.client.post(path, data=dict(fields or {}, csrf_token=token))

    def setup_owner(self, password='PrivateTestPass!123'):
        result = self.runner.invoke(args=['set-admin','--email','owner@example.test','--password',password])
        self.assertEqual(result.exit_code, 0, result.output)

    def login(self, password='PrivateTestPass!123'):
        return self.post('/admin/login', dict(email='owner@example.test',password=password))

    def count(self):
        with sqlite3.connect(self.database) as c:
            return c.execute('select count(*) from properties').fetchone()[0]

    def test_removed_features_and_public_pages(self):
        for path in ['/','/properties','/about','/contact','/sitemap.xml','/robots.txt','/admin/login']:
            r=self.client.get(path)
            self.assertEqual(r.status_code,200,path)
            self.assertNotIn(b'Favourites',r.data)
            self.assertNotIn(b'/verify-otp',r.data)
        for path in ['/login','/verify-otp','/logout','/favourites','/admin/favourites']:
            self.assertEqual(self.client.get(path).status_code,404)
        for template in module.app.jinja_env.list_templates():
            module.app.jinja_env.get_template(template)

    def test_no_default_and_all_mutations_protected(self):
        r=self.post('/admin/login',dict(email='admin@example.com',password='ChangeMe123!'))
        self.assertEqual(r.status_code,200)
        self.assertIn(b'Invalid email or password',r.data)
        for path in ['/admin','/admin/properties','/admin/properties/new','/admin/properties/1/edit','/admin/enquiries']:
            self.assertTrue(self.client.get(path).location.startswith('/admin/login'))
        for path in ['/admin/properties/new','/admin/properties/1/edit','/admin/properties/1/delete','/admin/images/1/delete','/admin/enquiries/1/read','/admin/enquiries/1/delete']:
            self.assertTrue(self.post(path).location.startswith('/admin/login'))
        self.assertEqual(self.count(),0)
        with self.client.session_transaction() as s:
            s['admin_id']=1
        self.assertTrue(self.client.get('/admin').location.startswith('/admin/login'))

    def test_owner_crud_csrf_logout_and_password_reset(self):
        self.setup_owner()
        self.assertEqual(self.login().location,'/admin')
        fields=dict(title='Owner house',property_type='House',purpose='Sale',price='100',location='Sector 68',city='Mohali',status='Available',published='on')
        self.assertEqual(self.client.post('/admin/properties/new',data=fields).status_code,400)
        self.assertEqual(self.post('/admin/properties/new',fields).status_code,302)
        self.assertEqual(self.count(),1)
        with sqlite3.connect(self.database) as c:
            slug=c.execute('select slug from properties').fetchone()[0]
        self.assertEqual(self.client.get('/property/'+slug).status_code,200)
        for path in ['/admin','/admin/properties','/admin/properties/new','/admin/properties/1/edit','/admin/enquiries']:
            self.assertEqual(self.client.get(path).status_code,200,path)
        self.assertEqual(self.client.get('/admin/properties/999/edit').status_code,404)
        self.assertEqual(self.post('/admin/properties/1/edit',fields).status_code,302)
        self.setup_owner('AnotherPrivatePass!123')
        self.assertTrue(self.client.get('/admin').location.startswith('/admin/login'))
        self.assertEqual(self.login().status_code,200)
        self.assertEqual(self.login('AnotherPrivatePass!123').location,'/admin')
        self.assertEqual(self.post('/admin/properties/1/delete').status_code,302)
        self.assertEqual(self.count(),0)
        self.assertEqual(self.client.get('/admin/logout').status_code,405)
        self.assertEqual(self.post('/admin/logout').status_code,302)
        self.assertTrue(self.client.get('/admin').location.startswith('/admin/login'))

    def test_setup_validation(self):
        r=self.runner.invoke(args=['set-admin','--email','owner@example.test','--password','short'])
        self.assertNotEqual(r.exit_code,0)

if __name__ == '__main__':
    unittest.main()
