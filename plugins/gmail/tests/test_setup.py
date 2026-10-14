import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "gmail_configure", PLUGIN_ROOT / "scripts" / "configure.py"
)
configure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(configure)


def client_config(port=8766):
    return {
        "web": {
            "client_id": "test.apps.googleusercontent.com",
            "client_secret": "fake-secret-never-print",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [f"http://localhost:{port}/oauth2callback"],
        }
    }


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.data = self.root / "private data"
        self.source = self.root / "download.json"
        self.source.write_text(json.dumps(client_config()))
        self.redirect = "http://localhost:8766/oauth2callback"

    def test_import_valid_client_and_check_private_permissions(self):
        destination = configure.import_client(self.source, self.data, self.redirect)
        self.assertEqual(json.loads(destination.read_text()), client_config())
        self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.data.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((self.data / "credentials").stat().st_mode), 0o700)
        with patch.object(configure.shutil, "which", return_value="/fake/uvx"):
            configure.check_setup(self.data, self.redirect)

    def test_wrong_client_type_or_callback_is_rejected_without_writing(self):
        for config in (
            {"installed": client_config()["web"]},
            client_config(port=9999),
            {"web": []},
            [],
        ):
            with self.subTest(config=config):
                self.source.write_text(json.dumps(config))
                with self.assertRaises(configure.SetupError):
                    configure.import_client(self.source, self.data, self.redirect)
                self.assertFalse(self.data.exists())

    def test_invalid_auth_endpoint_is_rejected(self):
        config = client_config()
        config["web"]["token_uri"] = "https://example.test/token"
        self.source.write_text(json.dumps(config))
        with self.assertRaises(configure.SetupError):
            configure.import_client(self.source, self.data, self.redirect)

    def test_reimport_is_safe_and_changing_clients_requires_replace(self):
        destination = configure.import_client(self.source, self.data, self.redirect)
        configure.import_client(self.source, self.data, self.redirect)
        config = client_config()
        config["web"]["client_secret"] = "different-fake-secret"
        self.source.write_text(json.dumps(config))
        with self.assertRaises(configure.SetupError):
            configure.import_client(self.source, self.data, self.redirect)
        self.assertEqual(json.loads(destination.read_text()), client_config())
        configure.import_client(self.source, self.data, self.redirect, replace=True)
        self.assertEqual(json.loads(destination.read_text()), config)

    def test_check_reports_public_file_permissions(self):
        destination = configure.import_client(self.source, self.data, self.redirect)
        destination.chmod(0o644)
        with patch.object(configure.shutil, "which", return_value="/fake/uvx"):
            with self.assertRaisesRegex(configure.SetupError, "mode 600"):
                configure.check_setup(self.data, self.redirect)

    def test_cli_never_prints_client_secret_on_success_or_failure(self):
        env = dict(os.environ, GMAIL_LOCAL_MCP_DATA_DIR=str(self.data), GMAIL_LOCAL_MCP_PORT="8766")
        result = subprocess.run(
            [sys.executable, str(PLUGIN_ROOT / "scripts/configure.py"),
             "--client-secrets", str(self.source)],
            env=env, text=True, capture_output=True, timeout=10,
        )
        self.assertNotIn("fake-secret-never-print", result.stdout + result.stderr)
        self.assertTrue((self.data / "client_secret.json").is_file())
        # An invalid file must not echo a JSON parser's source text or overwrite
        # a valid saved client.
        self.source.write_text('{"web": fake-secret-never-print}')
        result = subprocess.run(
            [sys.executable, str(PLUGIN_ROOT / "scripts/configure.py"),
             "--client-secrets", str(self.source), "--replace"],
            env=env, text=True, capture_output=True, timeout=10,
        )
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("fake-secret-never-print", result.stdout + result.stderr)
        self.assertEqual(json.loads((self.data / "client_secret.json").read_text()), client_config())


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        stub = self.bin / "uvx"
        stub.write_text(
            f"#!{sys.executable}\n"
            "import json, os, sys\n"
            "print(json.dumps({'args': sys.argv[1:], 'env': dict(os.environ), 'cwd': os.getcwd()}))\n"
        )
        stub.chmod(0o700)
        self.env = dict(
            os.environ,
            PATH=f"{self.bin}:/usr/bin:/bin",
            GMAIL_LOCAL_MCP_DATA_DIR=str(self.root / "private data"),
            GMAIL_LOCAL_MCP_PORT="18766",
        )

    def launch(self, **overrides):
        return subprocess.run(
            ["/bin/bash", str(PLUGIN_ROOT / "scripts/start.sh")],
            env=dict(self.env, **overrides), text=True, capture_output=True, timeout=10,
        )

    def test_unrelated_environment_cannot_change_account_or_callback(self):
        result = self.launch(
            PORT="9999", USER_GOOGLE_EMAIL="wrong@example.test",
            GOOGLE_OAUTH_CLIENT_ID="wrong-client", GOOGLE_OAUTH_CLIENT_SECRET="wrong-secret",
            GOOGLE_SERVICE_ACCOUNT_KEY_JSON="{}", WORKSPACE_MCP_HTTP_PORT="9998",
            WORKSPACE_MCP_PORT_FALLBACK_COUNT="4", MCP_SINGLE_USER_MODE="1",
            WORKSPACE_MCP_STATELESS_MODE="true", TRUST_GATEWAY_IDENTITY="true",
            WORKSPACE_MCP_CREDENTIAL_STORE_BACKEND="gcs",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        captured = json.loads(result.stdout)
        env = captured["env"]
        for key in (
            "PORT", "USER_GOOGLE_EMAIL", "GOOGLE_OAUTH_CLIENT_ID",
            "GOOGLE_OAUTH_CLIENT_SECRET", "GOOGLE_SERVICE_ACCOUNT_KEY_JSON",
            "WORKSPACE_MCP_HTTP_PORT",
        ):
            self.assertNotIn(key, env)
        self.assertEqual(env["WORKSPACE_MCP_PORT_FALLBACK_COUNT"], "0")
        self.assertEqual(env["GOOGLE_OAUTH_REDIRECT_URI"], "http://localhost:18766/oauth2callback")
        self.assertEqual(env["MCP_SINGLE_USER_MODE"], "0")
        self.assertEqual(env["WORKSPACE_MCP_CREDENTIAL_STORE_BACKEND"], "local_directory")
        self.assertEqual(env["WORKSPACE_MCP_STATELESS_MODE"], "false")
        self.assertEqual(env["TRUST_GATEWAY_IDENTITY"], "false")
        self.assertEqual(captured["cwd"], str((self.root / "private data").resolve()))
        self.assertIn("workspace-mcp==2.1.0", captured["args"])
        self.assertIn("gmail:drafts", captured["args"])

    def test_bad_port_or_relative_data_directory_fails_before_server_start(self):
        for port in ("0", "65536", "08766", "-1", "abc"):
            with self.subTest(port=port):
                result = self.launch(GMAIL_LOCAL_MCP_PORT=port)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
                self.assertIn("GMAIL_LOCAL_MCP_PORT", result.stderr)
        result = self.launch(GMAIL_LOCAL_MCP_DATA_DIR="relative/path")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("absolute path", result.stderr)


if __name__ == "__main__":
    unittest.main()
