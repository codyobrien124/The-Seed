#!/usr/bin/env python3
"""End-to-end tests for The Seed project."""

import json
import os
import shutil
import sys
import tempfile
import unittest

SEED_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SEED_DIR)


# ---------------------------------------------------------------------------
# senses.py
# ---------------------------------------------------------------------------

class TestSenses(unittest.TestCase):
    def setUp(self):
        import senses
        self.senses = senses
        self.inbox_path = os.path.join(SEED_DIR, "inbox.txt")
        self._original_inbox = ""
        if os.path.exists(self.inbox_path):
            with open(self.inbox_path) as f:
                self._original_inbox = f.read()
        with open(self.inbox_path, "w") as f:
            f.write("")

    def tearDown(self):
        with open(self.inbox_path, "w") as f:
            f.write(self._original_inbox)

    def test_returns_non_empty_string(self):
        result = self.senses.read_all()
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_expected_fields_present(self):
        result = self.senses.read_all()
        for field in ("Time:", "CPU:", "RAM:", "Disk:"):
            self.assertIn(field, result, f"Missing field: {field}")

    def test_inbox_message_read_and_cleared(self):
        with open(self.inbox_path, "w") as f:
            f.write("hello from test")
        result = self.senses.read_all()
        self.assertIn("hello from test", result)
        with open(self.inbox_path) as f:
            remaining = f.read()
        self.assertEqual(remaining, "", "Inbox was not cleared after read")

    def test_empty_inbox_no_message_line(self):
        result = self.senses.read_all()
        self.assertNotIn("Message from human:", result)

    def test_whitespace_only_inbox_ignored(self):
        with open(self.inbox_path, "w") as f:
            f.write("   \n  ")
        result = self.senses.read_all()
        self.assertNotIn("Message from human:", result)


# ---------------------------------------------------------------------------
# heartbeat.py file I/O
# ---------------------------------------------------------------------------

class TestHeartbeatIO(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_write_file_content(self):
        import heartbeat
        path = os.path.join(self.tmpdir, "test.txt")
        heartbeat.write_file(path, "hello world")
        with open(path) as f:
            self.assertEqual(f.read(), "hello world")

    def test_write_file_no_tmp_leftover(self):
        import heartbeat
        path = os.path.join(self.tmpdir, "test.txt")
        heartbeat.write_file(path, "content")
        self.assertFalse(os.path.exists(path + ".tmp"), ".tmp file left behind")

    def test_write_file_overwrites(self):
        import heartbeat
        path = os.path.join(self.tmpdir, "test.txt")
        heartbeat.write_file(path, "first")
        heartbeat.write_file(path, "second")
        with open(path) as f:
            self.assertEqual(f.read(), "second")

    def test_state_round_trip(self):
        import heartbeat
        orig = heartbeat.STATE_PATH
        heartbeat.STATE_PATH = os.path.join(self.tmpdir, "state.json")
        try:
            state = {"cycle": 42, "next_heartbeat_minutes": 15, "last_think_time": 3.7}
            heartbeat.save_state(state)
            loaded = heartbeat.load_state()
            self.assertEqual(loaded["cycle"], 42)
            self.assertEqual(loaded["next_heartbeat_minutes"], 15)
            self.assertAlmostEqual(loaded["last_think_time"], 3.7, places=5)
        finally:
            heartbeat.STATE_PATH = orig

    def test_save_state_no_tmp_leftover(self):
        import heartbeat
        orig = heartbeat.STATE_PATH
        heartbeat.STATE_PATH = os.path.join(self.tmpdir, "state.json")
        try:
            heartbeat.save_state({"cycle": 1})
            self.assertFalse(os.path.exists(heartbeat.STATE_PATH + ".tmp"))
        finally:
            heartbeat.STATE_PATH = orig

    def test_load_state_defaults_when_missing(self):
        import heartbeat
        orig = heartbeat.STATE_PATH
        heartbeat.STATE_PATH = os.path.join(self.tmpdir, "nonexistent.json")
        try:
            state = heartbeat.load_state()
            self.assertIn("cycle", state)
            self.assertEqual(state["cycle"], 0)
        finally:
            heartbeat.STATE_PATH = orig


# ---------------------------------------------------------------------------
# heartbeat.py JSON parsing logic
# ---------------------------------------------------------------------------

class TestJSONParsing(unittest.TestCase):
    """Tests for the inline JSON extraction logic in run_cycle."""

    @staticmethod
    def _parse(raw):
        clean = raw.strip()
        if "</think>" in clean:
            clean = clean.split("</think>")[-1]
        start, end = clean.find('{'), clean.rfind('}')
        if start != -1 and end != -1:
            clean = clean[start:end+1]
        return json.loads(clean)

    def test_strips_think_tags(self):
        raw = '<think>monologue</think>\n{"choice":"reflect","journal_entry":"ok","next_heartbeat_minutes":30}'
        resp = self._parse(raw)
        self.assertEqual(resp["choice"], "reflect")

    def test_extracts_embedded_json(self):
        raw = 'Sure, here you go:\n{"choice":"act","journal_entry":"done","next_heartbeat_minutes":10}\nDone.'
        resp = self._parse(raw)
        self.assertEqual(resp["choice"], "act")

    def test_bare_json(self):
        raw = '{"choice":"sleep","journal_entry":"quiet","next_heartbeat_minutes":60}'
        resp = self._parse(raw)
        self.assertEqual(resp["choice"], "sleep")

    def test_think_tag_with_embedded_json(self):
        raw = '<think>reasoning here</think>\nExtra text {"choice":"learn","journal_entry":"exp","next_heartbeat_minutes":5} trailing'
        resp = self._parse(raw)
        self.assertEqual(resp["choice"], "learn")


# ---------------------------------------------------------------------------
# grow.py parsing helpers
# ---------------------------------------------------------------------------

class TestGrowParsing(unittest.TestCase):
    def test_parse_full_header(self):
        from grow import _parse_journal_entry
        text = "5 | 2025-01-01 12:00:00 | choice: learn | took: 4.2s\nI tried something.\nExperiment: testing memory"
        choice, body, experiment = _parse_journal_entry(text)
        self.assertEqual(choice, "learn")
        self.assertIn("tried something", body)
        self.assertEqual(experiment, "testing memory")

    def test_parse_no_experiment(self):
        from grow import _parse_journal_entry
        text = "3 | 2025-01-02 09:00:00 | choice: sleep | took: 1.0s\nResting."
        choice, body, experiment = _parse_journal_entry(text)
        self.assertEqual(choice, "sleep")
        self.assertIsNone(experiment)

    def test_parse_no_header_defaults(self):
        from grow import _parse_journal_entry
        text = "Just plain text without a header."
        choice, body, experiment = _parse_journal_entry(text)
        self.assertEqual(choice, "reflect")
        self.assertIn("plain text", body)
        self.assertIsNone(experiment)

    def test_parse_act_choice(self):
        from grow import _parse_journal_entry
        text = "10 | 2025-02-01 08:00:00 | choice: act | took: 12.3s\nSent a message."
        choice, body, _ = _parse_journal_entry(text)
        self.assertEqual(choice, "act")

    def test_load_grow_state_defaults(self):
        import grow
        orig = grow.GROW_STATE_PATH
        grow.GROW_STATE_PATH = os.path.join(self.tmpdir if hasattr(self, 'tmpdir') else tempfile.mkdtemp(), "nonexistent.json")
        try:
            state = grow.load_grow_state()
            self.assertEqual(state["current_rank"], 2)
            self.assertEqual(state["train_count"], 0)
        finally:
            grow.GROW_STATE_PATH = orig


# ---------------------------------------------------------------------------
# portal.py routes
# ---------------------------------------------------------------------------

class TestPortalRoutes(unittest.TestCase):
    def setUp(self):
        import portal
        portal.app.config['TESTING'] = True
        self.client = portal.app.test_client()
        self.paths = portal.PATHS
        # Save/restore inbox and outbox
        self._saved = {}
        for key in ("inbox", "outbox"):
            p = self.paths[key]
            if os.path.exists(p):
                with open(p) as f:
                    self._saved[key] = f.read()
            else:
                self._saved[key] = ""

    def tearDown(self):
        for key, content in self._saved.items():
            with open(self.paths[key], "w") as f:
                f.write(content)

    def test_home_200(self):
        r = self.client.get('/')
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'Stan', r.data)

    def test_status_endpoint(self):
        r = self.client.get('/status')
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.data.decode(), str)

    def test_state_endpoint_shape(self):
        r = self.client.get('/state')
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        for key in ("cycle", "last_think_time", "sleep_until", "recent_choices"):
            self.assertIn(key, data, f"Missing key: {key}")

    def test_content_endpoint_shape(self):
        r = self.client.get('/content')
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        for key in ("outbox", "self_txt", "capabilities_txt", "journal"):
            self.assertIn(key, data, f"Missing key: {key}")

    def test_grow_state_endpoint_shape(self):
        r = self.client.get('/grow_state')
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertIn("current_rank", data)
        self.assertIn("train_count", data)

    def test_wake_returns_json_ok(self):
        r = self.client.post('/wake')
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertTrue(data.get("ok"))

    def test_send_writes_inbox_and_outbox(self):
        r = self.client.post('/send', data={"message": "e2e test message"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(json.loads(r.data).get("ok"))
        with open(self.paths["inbox"]) as f:
            self.assertEqual(f.read(), "e2e test message")
        with open(self.paths["outbox"]) as f:
            self.assertIn("e2e test message", f.read())

    def test_send_empty_message_no_error(self):
        r = self.client.post('/send', data={"message": "   "})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(json.loads(r.data).get("ok"))

    def test_content_journal_truncated(self):
        """Journal in /content should be at most 3000 chars."""
        r = self.client.get('/content')
        data = json.loads(r.data)
        self.assertLessEqual(len(data["journal"]), 3000)


if __name__ == "__main__":
    unittest.main(verbosity=2)
