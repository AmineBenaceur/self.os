"""End-to-end tests for the CLI and MCP server. Stdlib only: python -m unittest discover tests"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples" / "vault"
ENV = {**os.environ, "PYTHONPATH": str(ROOT)}


def cli(*args, vault=EXAMPLES):
    r = subprocess.run([sys.executable, "-m", "selfos", "--vault", str(vault), *args],
                       capture_output=True, text=True, encoding="utf-8", env=ENV, cwd=ROOT)
    return r.returncode, r.stdout


class CLITest(unittest.TestCase):
    def tearDown(self):
        (EXAMPLES / "INDEX.md").unlink(missing_ok=True)

    def test_examples_validate(self):
        code, out = cli("validate")
        self.assertEqual(code, 0, out)

    def test_every_command_runs(self):
        for cmd in ("goals", "habits", "review", "birthdays", "bundle", "index"):
            code, out = cli(cmd)
            self.assertEqual(code, 0, f"{cmd}: {out}")
        self.assertIn("Run a half marathon", cli("goals")[1])

    def test_init_creates_valid_vault(self):
        with tempfile.TemporaryDirectory() as d:
            v = Path(d) / "v"
            self.assertEqual(cli("init", vault=v)[0], 0)
            self.assertTrue((v / "profile" / "preferences.md").exists())
            self.assertEqual(cli("validate", vault=v)[0], 0)


class AgentCLITest(unittest.TestCase):
    def test_write_commands(self):
        with tempfile.TemporaryDirectory() as d:
            v = Path(d) / "v"
            cli("init", vault=v)
            goal = json.dumps({"title": "Run more", "description": "x", "why": ["fun"], "done_looks_like": "40 km",
                               "plan": ["When it is 6am, I run"], "metric": "km", "unit": "km",
                               "baseline": 0, "target": 40, "target_date": "2099-01-01"})
            self.assertEqual(cli("tool", "create_goal", goal, vault=v)[0], 0)
            self.assertEqual(cli("tool", "create_habit", json.dumps(
                {"title": "Run", "frequency": "3/week", "goal": "run-more"}), vault=v)[0], 0)
            code, out = cli("checkin", "Run more", "--value", "5", "good", vault=v)
            self.assertEqual(code, 0, out)
            self.assertEqual(json.loads(out)["goal"]["progress"]["latest"], 5)
            code, out = cli("log-habit", "run", "missed", "too", "cold", vault=v)
            self.assertEqual(json.loads(out)["habit"]["last_miss_reason"], "too cold")
            self.assertEqual(cli("note", "journal/2026-01-01", "hello", vault=v)[0], 0)
            self.assertEqual(cli("tool", "nope", vault=v)[0], 2)
            self.assertEqual(cli("context", vault=v)[0], 0)
            self.assertEqual(cli("validate", vault=v)[0], 0)


class MCPTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name) / "v"
        cli("init", vault=self.vault)
        self.proc = subprocess.Popen([sys.executable, "-m", "selfos", "--vault", str(self.vault), "mcp"],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                     text=True, encoding="utf-8", env=ENV, cwd=ROOT)
        self.n = 0
        init = self.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                       "clientInfo": {"name": "test", "version": "0"}})
        self.assertEqual(init["result"]["serverInfo"]["name"], "selfos")
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")

    def tearDown(self):
        self.proc.stdin.close()
        self.proc.wait(10)
        self.proc.stdout.close()
        self.tmp.cleanup()

    def rpc(self, method, params=None):
        self.n += 1
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self.n, "method": method, "params": params or {}}) + "\n")
        self.proc.stdin.flush()
        return json.loads(self.proc.stdout.readline())

    def call(self, name, **args):
        return self.rpc("tools/call", {"name": name, "arguments": args})["result"]

    def test_lists(self):
        names = {t["name"] for t in self.rpc("tools/list")["result"]["tools"]}
        self.assertTrue({"get_context", "create_goal", "log_goal_checkin", "log_habit", "weekly_review"} <= names)
        prompts = {p["name"] for p in self.rpc("prompts/list")["result"]["prompts"]}
        self.assertIn("set-goal", prompts)

    def test_coaching_loop(self):
        self.assertTrue(self.call("create_goal", title="Read more", description="12 books", why=["fun"],
                                  done_looks_like="12 books", plan=[]).get("isError"))
        r = self.call("create_goal", title="Read more", description="12 books", why=["fun"], done_looks_like="12 books",
                      plan=["When I board the train, I read"], metric="books", unit="books", baseline=0, target=12,
                      target_date="2099-12-31")
        self.assertFalse(r.get("isError"), r)
        self.assertFalse(self.call("create_habit", title="Read daily", frequency="daily", goal="Read more").get("isError"))
        self.assertFalse(self.call("log_habit", habit="read-daily", done=False, reason="tired").get("isError"))
        r = self.call("log_goal_checkin", goal="read-more", value=1)
        self.assertEqual(r["structuredContent"]["goal"]["progress"]["latest"], 1)
        self.assertTrue(self.call("update_goal", goal="read-more", status="paused").get("isError"))
        self.assertFalse(self.call("weekly_review").get("isError"))
        self.assertTrue(self.call("validate")["structuredContent"]["ok"])

    def test_path_escape_refused(self):
        self.assertTrue(self.call("read_file", path="../../secret").get("isError"))


if __name__ == "__main__":
    unittest.main()
