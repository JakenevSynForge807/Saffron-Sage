import sqlite3
import unittest
from unittest.mock import patch
from flask import render_template
import app as module

class SellerDashboardTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript('''
            CREATE TABLE dishesTable (id INTEGER PRIMARY KEY, dishname TEXT, dishprice REAL, sellerid INTEGER);
            CREATE TABLE orderTable (id INTEGER PRIMARY KEY, dishid INTEGER, status TEXT);
            CREATE TABLE cartItems (id INTEGER PRIMARY KEY, dishid INTEGER);
            INSERT INTO dishesTable VALUES (1, 'Soup', 8.5, 1), (2, 'Rice', 4, 2), (3, 'Cake', 5, 1);
            INSERT INTO orderTable VALUES (1, 1, 'pending'), (2, 2, 'pending');
            INSERT INTO cartItems VALUES (1, 3);
        ''')
        module.ensure_order_timestamps(self.conn)
        class Connection:
            execute = self.conn.execute
            commit = self.conn.commit
            def close(self): pass
        self.patch = patch.object(module, 'db', return_value=Connection())
        self.patch.start()
        module.app.config['TESTING'] = True
        self.client = module.app.test_client()
        with self.client.session_transaction() as session:
            session.update(id=1, role='seller')
    def tearDown(self):
        self.patch.stop()
        self.conn.close()
    def status(self, id=1):
        return self.conn.execute('SELECT status FROM orderTable WHERE id=?', (id,)).fetchone()[0]
    def test_status_transitions_and_ownership(self):
        self.client.post('/complete/1')
        self.assertEqual(self.status(), 'pending')
        self.client.post('/seller/accept/2')
        self.assertEqual(self.status(2), 'pending')
        self.client.post('/seller/accept/1')
        self.assertEqual(self.status(), 'accepted')
        self.client.post('/complete/1')
        self.assertEqual(self.status(), 'completed')
        self.client.post('/seller/cancel/1')
        self.client.post('/seller/accept/1')
        self.assertEqual(self.status(), 'completed')
    def test_delete_preserves_history_and_cleans_cart(self):
        self.client.post('/seller/delete/1')
        self.client.post('/seller/delete/2')
        self.assertEqual(self.conn.execute('SELECT count(*) FROM dishesTable').fetchone()[0], 3)
        self.client.post('/seller/delete/3')
        self.assertEqual(self.conn.execute('SELECT count(*) FROM cartItems').fetchone()[0], 0)
    def test_price_validation(self):
        for price in ['abc', 'NaN', 'Infinity', '-1', '0', '1.234', '1000000']:
            self.client.post('/seller/add', data={'dishname': 'Test', 'dishprice': price})
        self.assertEqual(self.conn.execute('SELECT count(*) FROM dishesTable').fetchone()[0], 3)
        self.client.post('/seller/add', data={'dishname': 'Test', 'dishprice': '12.25'})
        self.assertEqual(self.conn.execute('SELECT count(*) FROM dishesTable').fetchone()[0], 4)
    def test_modal_rendering_and_escaping(self):
        with module.app.test_request_context('/dashboard'):
            html = render_template('seller_dashboard.html', my_dishes=[{'id':1,'dishname':'Soup','dishprice':8.5}], totalDishes=1, pendingCount=0, acceptedCount=1, completedSales=12.5, my_orders=[dict(items=[{'dish':'Soup','quantity':2}],id=1,buyer='Buyer',recipient='Recipient',dish='Soup',quantity=2,status='accepted',phone='01234',deliveryAddress='Test address',notes='<script>alert(1)</script>',paymentMethod='cash')])
        self.assertIn('order-details-1', html)
        self.assertIn('Recipient', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('12.50', html)
        self.assertIn('8.50', html)
        self.assertIn('/complete/1', html)



class OrderHistoryTests(unittest.TestCase):
    def test_migration_routes_and_visibility(self):
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        conn.executescript('''
            CREATE TABLE usersInfo(id INTEGER PRIMARY KEY, fullname TEXT);
            CREATE TABLE dishesTable(id INTEGER PRIMARY KEY, dishname TEXT, dishprice REAL, sellerid INTEGER);
            CREATE TABLE orderTable(id INTEGER PRIMARY KEY, dishid INTEGER, buyerid INTEGER, quantity INTEGER,
                status TEXT, fullname TEXT, phone TEXT, deliveryAddress TEXT, notes TEXT, paymentMethod TEXT);
            INSERT INTO usersInfo VALUES(10, 'Test buyer'), (1, 'Seller'), (2, 'Other seller');
            INSERT INTO dishesTable VALUES(1, 'Active soup', 8.5, 1), (2, 'Finished cake', 4, 1), (3, 'Private dish', 5, 2);
            INSERT INTO orderTable(id,dishid,buyerid,quantity,status) VALUES(1,1,10,1,'pending');
        ''')
        module.ensure_order_timestamps(conn)
        module.ensure_order_timestamps(conn)
        self.assertIsNone(conn.execute('SELECT created_at FROM orderTable').fetchone()[0])
        conn.executescript('''
            INSERT INTO orderTable(id,dishid,buyerid,quantity,status) VALUES(2,2,10,1,'completed');
            INSERT INTO orderTable(id,dishid,buyerid,quantity,status) VALUES(3,3,10,1,'cancelled');
        ''')
        self.assertIsNotNone(conn.execute('SELECT created_at FROM orderTable WHERE id=2').fetchone()[0])
        class Connection:
            execute = conn.execute
            commit = conn.commit
            def close(self): pass
        client = module.app.test_client()
        with patch.object(module, 'db', return_value=Connection()):
            self.assertEqual(client.get('/seller/history').status_code, 302)
            with client.session_transaction() as session: session.update(id=1, role='seller')
            dashboard = client.get('/dashboard').get_data(as_text=True)
            # The incoming order table excludes the finished dish (it remains in the dish listing).
            incoming = dashboard.split('<div class="incoming-orders">')[1]
            self.assertIn('Active soup', incoming)
            self.assertNotIn('Finished cake', incoming)
            history = client.get('/seller/history').get_data(as_text=True)
            self.assertIn('Finished cake', history)
            self.assertIn('Active soup', history)
            self.assertNotIn('Private dish', history)
            self.assertNotIn('action-complete', history)
            self.assertIn('UTC', history)
            with client.session_transaction() as session: session.update(id=10, role='buyer')
            self.assertEqual(client.get('/seller/history').status_code, 403)
            buyer = client.get('/myorders')
            self.assertEqual(buyer.status_code, 200)
            self.assertIn('Date unavailable', buyer.get_data(as_text=True))
            self.assertIn('UTC', buyer.get_data(as_text=True))
        conn.close()

if __name__ == "__main__":
    unittest.main()
