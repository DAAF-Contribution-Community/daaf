"""Tests for scripts/provider_shim/render_codex_config.py (Codex config.toml renderer).

The renderer turns DAAF_CODEX_CONFIG_<N> lines from environment_settings.txt (plus
a derived gateway provider on the openai lane) into $CODEX_HOME/config.toml. Each
test runs the real CLI as a subprocess with a fixed, allowlisted environment (never
the parent's, so no real credential or CODEX_HOME can leak in) and an isolated
CODEX_HOME under scripts/scratch that is removed afterwards.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tomllib
import unittest
import uuid

from ._loopback_harness import DAAF_ROOT, SCRATCH_ROOT

RENDERER = DAAF_ROOT / "scripts/provider_shim/render_codex_config.py"
MARKER_PREFIX = "# Managed by DAAF"
SECRET_ONE = "sk-FAKE_RENDERER_SECRET_ONE_0000000000"
SECRET_TWO = "sk-FAKE_RENDERER_SECRET_TWO_0000000000"
GATEWAY_URL = "https://api.toolkit.example.edu/v1"


class RenderCodexConfigTests(unittest.TestCase):
    maxDiff = 8000

    def setUp(self) -> None:
        SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
        self.root = SCRATCH_ROOT / f"render-codex-config-unittest-{uuid.uuid4().hex}"
        self.root.mkdir(mode=0o700)
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.codex_home = self.root / "codex-home"
        self.config = self.codex_home / "config.toml"
        self.sidecar = self.codex_home / "config.toml.daaf-generated"

    def render(self, env: dict[str, str], *args: str) -> subprocess.CompletedProcess:
        child_env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8", "HOME": str(self.root)}
        child_env.update(env)
        return subprocess.run(
            [sys.executable, str(RENDERER), "--codex-home", str(self.codex_home), *args],
            env=child_env,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def load(self, path=None) -> dict:
        text = (path or self.config).read_text(encoding="utf-8")
        self.assertTrue(text.startswith(MARKER_PREFIX), text)
        return tomllib.loads(text)

    # --- ordering and value parsing -------------------------------------------------

    def test_numeric_order_later_entries_override(self) -> None:
        result = self.render({
            "DAAF_CODEX_CONFIG_10": 'model="ten"',
            "DAAF_CODEX_CONFIG_2": 'model="two"',
            "DAAF_CODEX_CONFIG_1": 'model="one"',
        })
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.load(), {"model": "ten"})

    def test_misnamed_variables_are_reported_by_name_only(self) -> None:
        result = self.render({
            "DAAF_CODEX_CONFIG_0": 'ignored_zero="VALUE_ZERO"',
            "DAAF_CODEX_CONFIG_X": 'ignored_alpha="VALUE_ALPHA"',
            "DAAF_CODEX_CONFIG_": 'ignored_blank="VALUE_BLANK"',
            "DAAF_CODEX_CONFIG": 'ignored_bare="VALUE_BARE"',
            "daaf_codex_config_3": 'ignored_lower="VALUE_LOWER"',
            "DAAF_CODEX_CONFIG_2": 'model="kept"',
        })
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr.count(" ignored: the name must be"), 5, result.stderr)
        for name in ("DAAF_CODEX_CONFIG_0", "DAAF_CODEX_CONFIG_X", "daaf_codex_config_3"):
            self.assertIn(name, result.stderr)
        self.assertNotIn("VALUE_", result.stderr + result.stdout)
        self.assertEqual(self.load(), {"model": "kept"})

    def test_zero_padded_numbers_are_accepted_and_duplicates_warned(self) -> None:
        result = self.render({"DAAF_CODEX_CONFIG_01": 'model="padded"', "DAAF_CODEX_CONFIG_2": "x=1"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.load(), {"model": "padded", "x": 1})
        result = self.render({"DAAF_CODEX_CONFIG_01": 'model="first"', "DAAF_CODEX_CONFIG_1": 'model="second"'})
        self.assertEqual(result.returncode, 2)
        self.assertIn("all use number 1", result.stderr)
        self.assertEqual(self.load(), {"model": "second"})  # applied in name order

    def test_toml_values_and_literal_string_fallback(self) -> None:
        result = self.render({
            "DAAF_CODEX_CONFIG_1": "model_reasoning_effort=high",
            "DAAF_CODEX_CONFIG_2": "count=42",
            "DAAF_CODEX_CONFIG_3": "flag=true",
            "DAAF_CODEX_CONFIG_4": 'items=["a", "b"]',
            "DAAF_CODEX_CONFIG_5": 'quoted="has = sign"',
            "DAAF_CODEX_CONFIG_6": "spaced=1 2",
            "DAAF_CODEX_CONFIG_7": "injected=1\nother=2",
            "DAAF_CODEX_CONFIG_8": "'single=\"wrapped\"'",
        })
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.load(), {
            "model_reasoning_effort": "high",
            "count": 42,
            "flag": True,
            "items": ["a", "b"],
            "quoted": "has = sign",
            "spaced": "1 2",
            "injected": "1\nother=2",
            "single": "wrapped",
        })

    def test_nested_tables_and_inline_tables(self) -> None:
        result = self.render({
            "DAAF_CODEX_CONFIG_1": 'model_provider="toolkit"',
            "DAAF_CODEX_CONFIG_2": 'model_providers.toolkit.name="Example Gateway"',
            "DAAF_CODEX_CONFIG_3": f'model_providers.toolkit.base_url="{GATEWAY_URL}"',
            "DAAF_CODEX_CONFIG_4": "model_providers.toolkit.requires_openai_auth=true",
            "DAAF_CODEX_CONFIG_5": 'model_providers.other={ name = "O", wire_api = "responses" }',
            "DAAF_CODEX_CONFIG_6": 'profiles.fast.model="gpt-fast"',
        })
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.load(), {
            "model_provider": "toolkit",
            "model_providers": {
                "toolkit": {
                    "name": "Example Gateway",
                    "base_url": GATEWAY_URL,
                    "requires_openai_auth": True,
                },
                "other": {"name": "O", "wire_api": "responses"},
            },
            "profiles": {"fast": {"model": "gpt-fast"}},
        })

    def test_quoted_key_segments(self) -> None:
        result = self.render({
            "DAAF_CODEX_CONFIG_1": 'projects."/daaf".trust_level="trusted"',
            "DAAF_CODEX_CONFIG_2": "projects.'/srv/data'.trust_level = \"trusted\"",
            "DAAF_CODEX_CONFIG_3": 'projects."a=b.c".note="eq and dot inside quotes"',
            "DAAF_CODEX_CONFIG_4": 'projects."unterminated.x=1',
        })
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr.count("skipped"), 1, result.stderr)
        self.assertEqual(self.load(), {"projects": {
            "/daaf": {"trust_level": "trusted"},
            "/srv/data": {"trust_level": "trusted"},
            "a=b.c": {"note": "eq and dot inside quotes"},
        }})

    def test_trust_inline_table_example_from_template(self) -> None:
        result = self.render({"DAAF_CODEX_CONFIG_1": 'projects={"/daaf"={trust_level="trusted"}}'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.load(), {"projects": {"/daaf": {"trust_level": "trusted"}}})

    def test_table_scalar_conflicts_later_entry_wins_in_both_orders(self) -> None:
        result = self.render({
            "DAAF_CODEX_CONFIG_1": "a.b=1",
            "DAAF_CODEX_CONFIG_2": "a.b.c=2",
            "DAAF_CODEX_CONFIG_3": "d.e.f=2",
            "DAAF_CODEX_CONFIG_4": "d.e=1",
        })
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.load(), {"a": {"b": {"c": 2}}, "d": {"e": 1}})

    def test_non_finite_floats_refused_per_entry(self) -> None:
        result = self.render({
            "DAAF_CODEX_CONFIG_1": "bad=nan",
            "DAAF_CODEX_CONFIG_2": "worse=[1.0, -inf]",
            "DAAF_CODEX_CONFIG_3": "nested={x=inf}",
            "DAAF_CODEX_CONFIG_4": "good=1.5",
        })
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr.count("nan or inf"), 3, result.stderr)
        self.assertEqual(self.load(), {"good": 1.5})

    def test_empty_value_is_skipped_with_warning(self) -> None:
        result = self.render({
            "DAAF_CODEX_CONFIG_1": "model=",
            "DAAF_CODEX_CONFIG_2": "model_reasoning_effort=   ",
            "DAAF_CODEX_CONFIG_3": 'empty_string=""',
        })
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr.count("has no value"), 2, result.stderr)
        self.assertEqual(self.load(), {"empty_string": ""})

    # --- derived gateway defaults ---------------------------------------------------

    def test_openai_lane_gateway_is_derived(self) -> None:
        result = self.render({
            "SHIM_BACKEND_MODE": "openai",
            "SHIM_BACKEND_BASE_URL": f" {GATEWAY_URL}/responses/ ",
            "ANTHROPIC_DEFAULT_OPUS_MODEL": "openai/gpt-5.6-terra[1m] #high",
            "OPENAI_API_KEY": SECRET_ONE,
        })
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.load(), {
            "model_provider": "daaf_gateway",
            "model": "gpt-5.6-terra",
            "model_providers": {
                "daaf_gateway": {
                    "name": "DAAF gateway (SHIM_BACKEND_BASE_URL)",
                    "base_url": GATEWAY_URL,
                    "env_key": "OPENAI_API_KEY",
                    "wire_api": "responses",
                }
            },
        })
        self.assertNotIn(SECRET_ONE, self.config.read_text(encoding="utf-8"))
        self.assertNotIn(SECRET_ONE, result.stderr + result.stdout)

    def test_shim_backend_api_key_name_wins_for_env_key(self) -> None:
        result = self.render({
            "SHIM_BACKEND_MODE": "openai",
            "SHIM_BACKEND_BASE_URL": GATEWAY_URL,
            "SHIM_BACKEND_API_KEY": SECRET_TWO,
        })
        self.assertEqual(result.returncode, 0, result.stderr)
        config = self.load()
        self.assertEqual(config["model_providers"]["daaf_gateway"]["env_key"], "SHIM_BACKEND_API_KEY")
        self.assertNotIn("model", config)  # no ANTHROPIC_DEFAULT_OPUS_MODEL -> skipped
        self.assertNotIn(SECRET_TWO, self.config.read_text(encoding="utf-8"))

    def test_nothing_derived_for_default_url_or_chatgpt_lane(self) -> None:
        cases = [
            {"SHIM_BACKEND_MODE": "openai", "SHIM_BACKEND_BASE_URL": "https://api.openai.com/v1/"},
            {"SHIM_BACKEND_MODE": "openai"},
            {"SHIM_BACKEND_MODE": "chatgpt", "SHIM_BACKEND_BASE_URL": GATEWAY_URL},
            {"SHIM_BACKEND_BASE_URL": GATEWAY_URL},
        ]
        for env in cases:
            with self.subTest(env=env):
                env = dict(env, ANTHROPIC_DEFAULT_OPUS_MODEL="gpt-5.6-terra[1m]")
                result = self.render(env)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertFalse(self.codex_home.exists())
                self.assertEqual(result.stderr, "")

    def test_chatgpt_lane_renders_only_explicit_entries(self) -> None:
        result = self.render({
            "SHIM_BACKEND_MODE": "chatgpt",
            "SHIM_BACKEND_BASE_URL": GATEWAY_URL,
            "DAAF_CODEX_CONFIG_1": 'model_reasoning_effort="medium"',
        })
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.load(), {"model_reasoning_effort": "medium"})

    def test_explicit_entries_override_derived_values(self) -> None:
        result = self.render({
            "SHIM_BACKEND_MODE": "openai",
            "SHIM_BACKEND_BASE_URL": GATEWAY_URL,
            "ANTHROPIC_DEFAULT_OPUS_MODEL": "gpt-5.6-terra[1m]",
            "DAAF_CODEX_CONFIG_1": 'model="gpt-other"',
            "DAAF_CODEX_CONFIG_2": 'model_providers.daaf_gateway.name="Example Gateway"',
            "DAAF_CODEX_CONFIG_3": 'model_provider="toolkit"',
        })
        self.assertEqual(result.returncode, 0, result.stderr)
        config = self.load()
        self.assertEqual(config["model"], "gpt-other")
        self.assertEqual(config["model_provider"], "toolkit")
        self.assertEqual(config["model_providers"]["daaf_gateway"]["name"], "Example Gateway")
        self.assertEqual(config["model_providers"]["daaf_gateway"]["base_url"], GATEWAY_URL)

    # --- secret guard ---------------------------------------------------------------

    def test_secret_keys_are_refused_without_echoing_values(self) -> None:
        result = self.render({
            "DAAF_CODEX_CONFIG_1": f'model_providers.x.experimental_bearer_token="{SECRET_ONE}"',
            "DAAF_CODEX_CONFIG_2": f'model_providers.x.http_headers={{ Authorization = "Bearer {SECRET_TWO}" }}',
            "DAAF_CODEX_CONFIG_3": f"API_KEY={SECRET_ONE}",
            "DAAF_CODEX_CONFIG_4": 'model="kept"',
            "DAAF_CODEX_CONFIG_5": "model_auto_compact_token_limit=100000",
        })
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr.count("refused"), 3, result.stderr)
        self.assertIn("env_key", result.stderr)
        text = self.config.read_text(encoding="utf-8")
        for secret in (SECRET_ONE, SECRET_TWO):
            self.assertNotIn(secret, text)
            self.assertNotIn(secret, result.stderr)
            self.assertNotIn(secret, result.stdout)
        self.assertEqual(self.load(), {"model": "kept", "model_auto_compact_token_limit": 100000})

    def test_header_query_and_credential_shaped_values_refused(self) -> None:
        # Shapes that leaked past the original key-name deny-list (review repros).
        result = self.render({
            "DAAF_CODEX_CONFIG_1": f"model_providers.g.http_headers.Ocp-Apim-Subscription-Key={SECRET_ONE}",
            "DAAF_CODEX_CONFIG_2": "model_providers.g.http_headers.Cookie=session=FAKE_COOKIE_VALUE",
            "DAAF_CODEX_CONFIG_3": "model_providers.g.query_params.key=FAKE_QUERY_VALUE",
            "DAAF_CODEX_CONFIG_4": f'model_providers.g.http_headers={{"x-token-ish"="{SECRET_TWO}"}}',
            "DAAF_CODEX_CONFIG_5": "model_providers.g.http_headers.X-Team=FAKE_PLAIN_HEADER",
            "DAAF_CODEX_CONFIG_6": f'model="{SECRET_ONE}"',
            "DAAF_CODEX_CONFIG_7": 'notes=["ok", "Bearer FAKE_BEARER_VALUE"]',
            "DAAF_CODEX_CONFIG_8": "model_providers.g.subscriptionkey=FAKE_SUBKEY_VALUE",
            "DAAF_CODEX_CONFIG_9": 'model_providers={g={http_headers={Cookie="FAKE_NESTED_VALUE"}}}',
            "DAAF_CODEX_CONFIG_10": 'model_providers.g.name="kept"',
        })
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr.count("refused"), 9, result.stderr)
        self.assertIn("env_http_headers", result.stderr)
        text = self.config.read_text(encoding="utf-8")
        for fake in (SECRET_ONE, SECRET_TWO, "FAKE_COOKIE_VALUE", "FAKE_QUERY_VALUE", "FAKE_PLAIN_HEADER",
                     "FAKE_BEARER_VALUE", "FAKE_SUBKEY_VALUE", "FAKE_NESTED_VALUE"):
            self.assertNotIn(fake, text)
            self.assertNotIn(fake, result.stderr + result.stdout)
        self.assertEqual(self.load(), {"model_providers": {"g": {"name": "kept"}}})

    def test_environment_variable_pointers_are_accepted(self) -> None:
        result = self.render({
            # The inline table comes first: a later whole-table entry would replace it.
            "DAAF_CODEX_CONFIG_1": 'model_providers.g.env_http_headers={"Ocp-Apim-Subscription-Key"="SUB_ENV", Cookie="COOKIE_ENV"}',
            "DAAF_CODEX_CONFIG_2": "model_providers.g.env_http_headers.X-Api-Key=MY_ENV_VAR",
            "DAAF_CODEX_CONFIG_3": 'model_providers.g.env_key="GATEWAY_API_KEY"',
            "DAAF_CODEX_CONFIG_4": 'mcp_servers.s.bearer_token_env_var="MCP_TOKEN"',
            "DAAF_CODEX_CONFIG_5": 'model_providers.g.query_params={api-version="2025-04-01-preview"}',
        })
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.load(), {
            "model_providers": {"g": {
                "env_http_headers": {"X-Api-Key": "MY_ENV_VAR", "Ocp-Apim-Subscription-Key": "SUB_ENV",
                                     "Cookie": "COOKIE_ENV"},
                "env_key": "GATEWAY_API_KEY",
                "query_params": {"api-version": "2025-04-01-preview"},
            }},
            "mcp_servers": {"s": {"bearer_token_env_var": "MCP_TOKEN"}},
        })

    def test_credential_value_under_env_pointer_is_still_refused(self) -> None:
        result = self.render({"DAAF_CODEX_CONFIG_1": f"model_providers.g.env_http_headers.X-Api-Key={SECRET_ONE}"})
        self.assertEqual(result.returncode, 2)
        self.assertIn("refused", result.stderr)
        self.assertNotIn(SECRET_ONE, result.stderr + result.stdout)
        self.assertFalse(self.codex_home.exists())

    # --- run log --------------------------------------------------------------------

    def test_run_log_records_summary_and_warnings_without_values(self) -> None:
        log = self.root / "logs" / "codex_config.log"
        result = self.render({
            "DAAF_CODEX_CONFIG_1": 'model="logged"',
            "DAAF_CODEX_CONFIG_2": f'model_providers.g.http_headers.Cookie="{SECRET_ONE}"',
        }, "--log-file", str(log))
        self.assertEqual(result.returncode, 2)
        lines = log.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2, lines)
        self.assertIn(" warning: DAAF_CODEX_CONFIG_2 refused", lines[0])
        self.assertRegex(lines[1], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ summary: wrote 1 setting\(s\) .*1 problem\(s\).*\(exit 2\)$")
        self.assertNotIn(SECRET_ONE, log.read_text(encoding="utf-8"))
        self.assertEqual(stat.S_IMODE(log.stat().st_mode), 0o600)
        # Removing the settings is logged too, so --status never shows a stale line.
        self.assertEqual(self.render({}, "--log-file", str(log)).returncode, 0)
        self.assertIn("summary: no Codex settings configured; removed", log.read_text(encoding="utf-8").splitlines()[-1])

    def test_run_log_is_bounded_and_not_created_for_a_silent_no_op(self) -> None:
        log = self.root / "logs" / "codex_config.log"
        self.assertEqual(self.render({}, "--log-file", str(log)).returncode, 0)
        self.assertFalse(log.exists())
        log.parent.mkdir(mode=0o700)
        log.write_text("".join(f"old line {i}\n" for i in range(500)), encoding="utf-8")
        self.assertEqual(self.render({"DAAF_CODEX_CONFIG_1": "x=1"}, "--log-file", str(log)).returncode, 0)
        lines = log.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 200)
        self.assertIn("summary: wrote 1 setting(s)", lines[-1])

    def test_run_log_symlink_is_not_followed(self) -> None:
        log_dir = self.root / "logs"
        log_dir.mkdir(mode=0o700)
        referent = self.root / "referent.txt"
        referent.write_text("unchanged\n", encoding="utf-8")
        (log_dir / "codex_config.log").symlink_to(referent)
        result = self.render({"DAAF_CODEX_CONFIG_1": "x=1"}, "--log-file", str(log_dir / "codex_config.log"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("run log not written", result.stderr)
        self.assertEqual(referent.read_text(encoding="utf-8"), "unchanged\n")

    # --- file ownership -------------------------------------------------------------

    def test_user_authored_file_is_preserved_and_sidecar_written(self) -> None:
        self.codex_home.mkdir(mode=0o700)
        original = 'model = "mine"\n'
        self.config.write_text(original, encoding="utf-8")
        result = self.render({"DAAF_CODEX_CONFIG_1": 'model="daaf"'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.config.read_text(encoding="utf-8"), original)
        self.assertIn("left alone", result.stderr)
        self.assertEqual(self.load(self.sidecar), {"model": "daaf"})
        # With nothing to render, the user's file is still untouched; the DAAF
        # sidecar is cleaned up.
        result = self.render({})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.config.read_text(encoding="utf-8"), original)
        self.assertFalse(self.sidecar.exists())

    def test_managed_file_is_removed_when_settings_are_removed(self) -> None:
        self.assertEqual(self.render({"DAAF_CODEX_CONFIG_1": 'model="a"'}).returncode, 0)
        self.assertTrue(self.config.exists())
        result = self.render({})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.config.exists())
        self.assertIn("removed", result.stderr)
        # A second empty run is a silent no-op.
        result = self.render({})
        self.assertEqual((result.returncode, result.stderr, result.stdout), (0, "", ""))

    def test_atomic_private_write_replaces_file(self) -> None:
        self.assertEqual(self.render({"DAAF_CODEX_CONFIG_1": 'model="a"'}).returncode, 0)
        first_inode = self.config.stat().st_ino
        self.assertEqual(stat.S_IMODE(self.config.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.codex_home.stat().st_mode), 0o700)
        self.assertEqual(self.render({"DAAF_CODEX_CONFIG_1": 'model="b"'}).returncode, 0)
        self.assertNotEqual(self.config.stat().st_ino, first_inode)  # renamed into place
        self.assertEqual(stat.S_IMODE(self.config.stat().st_mode), 0o600)
        self.assertEqual(self.load(), {"model": "b"})
        self.assertEqual(sorted(os.listdir(self.codex_home)), ["config.toml"])  # no temp left

    # --- invalid input and dry run --------------------------------------------------

    def test_invalid_entries_are_skipped_and_valid_ones_rendered(self) -> None:
        result = self.render({
            "DAAF_CODEX_CONFIG_1": "no_equals_sign",
            "DAAF_CODEX_CONFIG_2": "bad key!=1",
            "DAAF_CODEX_CONFIG_3": ".leading=1",
            "DAAF_CODEX_CONFIG_4": "   ",
            "DAAF_CODEX_CONFIG_5": 'model="ok"',
        })
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr.count("skipped"), 3, result.stderr)
        self.assertEqual(self.load(), {"model": "ok"})

    def test_empty_placeholder_is_not_an_error(self) -> None:
        result = self.render({"DAAF_CODEX_CONFIG_1": ""})
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        self.assertFalse(self.codex_home.exists())

    def test_dry_run_prints_and_writes_nothing(self) -> None:
        result = self.render({"DAAF_CODEX_CONFIG_1": 'model="dry"'}, "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith(MARKER_PREFIX))
        self.assertEqual(tomllib.loads(result.stdout), {"model": "dry"})
        self.assertFalse(self.codex_home.exists())


if __name__ == "__main__":
    unittest.main()
