import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app as module
from db import SCHEMA


class AIAssistantPageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "test.db"
        with sqlite3.connect(self.path) as conn:
            conn.executescript(SCHEMA)

        self.previous_testing = module.app.config.get("TESTING", False)
        module.app.config["TESTING"] = True
        self.db_patch = patch.object(module, "db", side_effect=self._test_db)
        self.db_patch.start()
        self.client = module.app.test_client()
        with self.client.session_transaction() as session:
            session.update(id=1, role="buyer", fullname="Test Buyer")

    def tearDown(self):
        self.db_patch.stop()
        module.app.config["TESTING"] = self.previous_testing
        self.temp.cleanup()

    def test_authenticated_user_can_open_ai_assistant(self):
        response = self.client.get("/ai-assistant")

        self.assertEqual(response.status_code, 200)
        self.assertIn("AI Menu Assistant", response.get_data(as_text=True))

    def _test_db(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn


if __name__ == "__main__":
    unittest.main()
