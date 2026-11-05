import contextlib
import importlib.util
import io
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RuntimeToolsTest(unittest.TestCase):
    def test_generated_secrets_are_unique_and_existing_config_is_preserved(self):
        init = load("init_runtime_env")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            init.initialize(path, "owner@example.com")
            original = path.read_bytes()
            self.assertNotIn(b"<GENERATE_", original)
            values = dict(line.split("=", 1) for line in original.decode().splitlines() if line and not line.startswith("#"))
            secrets = [values[key] for key in ("POSTGRES_PASSWORD", "REDIS_PASSWORD", "SECRET_KEY", "USER_LLM_CREDENTIAL_SECRET")]
            self.assertEqual(len(set(secrets)), 4)
            self.assertTrue(all(len(value) == 64 for value in secrets))
            with self.assertRaises(FileExistsError):
                init.initialize(path, "another@example.com")
            self.assertEqual(path.read_bytes(), original)
            with self.assertRaises(ValueError):
                init.initialize(Path(tmp) / "bad.env", "owner@example.com\nENV=production")

    def test_readiness_rejects_migration_failure_even_with_http_200(self):
        probe = load("check_runtime")
        state = {"migrations": "up"}

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                body = b"ok" if self.path == "/healthz" else ('{"data":{"services":{"api":"up","database":"up","redis":"up","migrations":"' + state["migrations"] + '"}}}').encode()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}"
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertTrue(probe.check(url, url))
                state["migrations"] = "down"
                self.assertFalse(probe.check(url, url))
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
