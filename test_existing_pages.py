import ast
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import closing
import app as module

class ExistingPagesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'test.db'
        source = ast.parse(Path('init_db.py').read_text())
        schema = next(node.value.args[0].value for node in source.body if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute) and node.value.func.attr == 'executescript')
        conn = sqlite3.connect(self.path)
        conn.executescript(schema)
        conn.executescript('''
            INSERT INTO usersInfo(id,fullname,email,password,role) VALUES
            (1,'Seller','seller@example.test','unused','seller'),
            (2,'Buyer','buyer@example.test','unused','buyer');
            INSERT INTO dishesTable(id,dishname,dishprice,sellerid) VALUES (1,'Test Soup',8.25,1);
        ''')
        conn.close()
        def test_db():
            conn = sqlite3.connect(self.path)
            conn.row_factory = sqlite3.Row
            module.ensure_order_timestamps(conn)
            return conn
        self.patch = patch.object(module, 'db', side_effect=test_db)
        self.patch.start()
        module.app.config['TESTING'] = True
        self.client = module.app.test_client()
    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()
    def login(self, role='buyer'):
        with self.client.session_transaction() as session:
            session.update(id=2 if role=='buyer' else 1, role=role, fullname=role)
    def count(self, table):
        with closing(sqlite3.connect(self.path)) as conn:
            return conn.execute('SELECT count(*) FROM '+table).fetchone()[0]
    def test_public_pages_and_dynamic_menu(self):
        for path in ['/', '/menu', '/reservations', '/about', '/contactus', '/login', '/signup']:
            self.assertEqual(self.client.get(path).status_code, 200, path)
        html = self.client.get('/').get_data(as_text=True)
        self.assertIn('href="/menu"', html)
        self.assertIn('href="/reservations"', html)
        self.assertIn('Test Soup', self.client.get('/menu').get_data(as_text=True))
        self.assertEqual(self.client.get('/reservations').get_data(as_text=True).count('<html'), 1)
    def test_cart_checkout_and_seller_flow(self):
        self.login()
        self.assertEqual(self.client.post('/checkout', data={}).status_code, 302)
        self.assertEqual(self.count('orderTable'), 0)
        for quantity in ['0', '-1', '21', 'abc', '1.5']:
            self.client.post('/cart/add/1', data={'quantity':quantity})
        self.client.post('/cart/add/999', data={'quantity':'1'})
        self.assertEqual(self.count('cartItems'), 0)
        self.client.post('/cart/add/1', data={'quantity':'2'})
        html = self.client.get('/checkout').get_data(as_text=True)
        self.assertIn('16.50', html)
        self.assertIn('19.00', html)
        self.client.post('/checkout', data={'fullname':'', 'phone':'', 'deliveryAddress':'', 'paymentMethod':'fake'})
        self.assertEqual(self.count('orderTable'), 0)
        response = self.client.post('/checkout', data={'fullname':'Test Buyer','phone':'+44 123','deliveryAddress':'Test address','paymentMethod':'cash'}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.count('orderTable'), 1)
        self.assertEqual(self.count('cartItems'), 0)
        self.assertIn('Order placed!', response.get_data(as_text=True))
        self.client.post('/checkout', data={})
        self.assertEqual(self.count('orderTable'), 1)
        self.login('seller')
        self.client.post('/seller/accept/1')
        self.client.post('/complete/1')
        self.assertEqual(self.client.get('/seller/history').status_code, 200)
        self.assertEqual(self.client.get('/dashboard').status_code, 200)
    def test_signup_validation_and_login(self):
        for data in [{}, {'fullname':'Test','email':'test@example.test','password':'123456','role':'admin'}, {'fullname':'Test','email':'test@example.test','password':'123','role':'buyer'}]:
            self.client.post('/signup', data=data)
        self.assertEqual(self.count('usersInfo'), 2)
        self.client.post('/signup', data={'fullname':'Test','email':'test@example.test','password':'123456','role':'buyer'})
        self.assertEqual(self.count('usersInfo'), 3)
        response = self.client.post('/login', data={'email':'test@example.test','password':'123456'}, follow_redirects=True)
        self.assertIn('Browse Dishes', response.get_data(as_text=True))
    def test_reservations_and_contact(self):
        self.client.post('/reservations', data={})
        self.assertEqual(self.count('reservations'), 0)
        response = self.client.post('/reservations', data={'first_name':'A','last_name':'B','email':'a@example.test','date':'2099-01-01','time':'18:00','guests':'2','seating':'indoor','terms':'on'}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.count('reservations'), 1)
        self.client.get('/reservations')
        self.assertEqual(self.count('reservations'), 1)
        self.client.post('/contactus', data={})
        self.assertEqual(self.count('contact'), 0)
        self.client.post('/contactus', data={'name':'Test','email':'a@example.test','message':'Hello'}, follow_redirects=True)
        self.assertEqual(self.count('contact'), 1)

    def test_grouped_orders_and_whole_order_actions(self):
        with closing(sqlite3.connect(self.path)) as conn:
            conn.executescript("""
                INSERT INTO usersInfo(id,fullname,email,password,role)
                    VALUES(3,'Other Seller','other@example.test','unused','seller');
                INSERT INTO dishesTable(id,dishname,dishprice,sellerid)
                    VALUES(2,'Second dish',4.5,1),(3,'Other seller dish',3,3);
            """)
        self.login()
        for dish, quantity in [(1,2),(2,1),(3,1)]:
            self.client.post(f'/cart/add/{dish}', data={'quantity':quantity})
        details = {'fullname':'Buyer','phone':'123','deliveryAddress':'Test','paymentMethod':'cash'}
        self.client.post('/checkout', data=details)
        with closing(module.db()) as conn:
            orders = module.get_orders(conn, 2, 'buyer')
            self.assertEqual(len(orders), 2)
            grouped = next(order for order in orders if order['sellerid'] == 1)
            separate = next(order for order in orders if order['sellerid'] == 3)
            self.assertEqual(len(grouped['items']), 2)
            self.assertEqual(grouped['quantity'], 3)
            self.assertEqual(grouped['total'], 21)
            self.assertEqual(len(module.get_orders(conn, 1, 'seller')), 1)
            order_id = grouped['id']
        buyer_html = self.client.get('/myorders').get_data(as_text=True)
        self.assertEqual(buyer_html.count(f'Order #{order_id}</strong>'), 1)
        self.login('seller')
        self.client.post(f'/seller/accept/{order_id}')
        self.client.post(f'/complete/{order_id}')
        self.client.post(f'/seller/accept/{separate["id"]}')
        with closing(module.db()) as conn:
            statuses = conn.execute('SELECT status FROM orderTable WHERE order_group_id=?', (order_id,)).fetchall()
            self.assertEqual([row[0] for row in statuses], ['completed', 'completed'])
            self.assertEqual(module.get_orders(conn, 3, 'seller')[0]['status'], 'pending')
        # A later checkout with the same seller must get its own order number.
        self.login()
        for dish in [1,2]:
            self.client.post(f'/cart/add/{dish}', data={'quantity':1})
        self.client.post('/checkout', data=details)
        with closing(module.db()) as conn:
            latest = module.get_orders(conn, 2, 'buyer')[0]
            self.assertNotEqual(latest['id'], order_id)
        self.client.post(f'/order/cancel/{latest["id"]}')
        with closing(module.db()) as conn:
            statuses = conn.execute('SELECT status FROM orderTable WHERE order_group_id=?', (latest['id'],)).fetchall()
            self.assertEqual([row[0] for row in statuses], ['cancelled', 'cancelled'])

if __name__ == '__main__':
    unittest.main()
