#!/usr/bin/env python3
"""
Testes de regressão para lib/claude_exporter.py.

Rodar:  python3 tests/test_claude_exporter.py

Foco principal: SEGURANÇA (remoção de segredos e generalização de paths) e a
lógica de detecção de language servers / flags. Só stdlib.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

LIB = Path(__file__).resolve().parent.parent / "lib"
sys.path.insert(0, str(LIB))
import claude_exporter as ce  # type: ignore  # noqa: E402


class TestCatalog(unittest.TestCase):
    def test_core_sections(self):
        cat = ce.load_catalog()
        for key in ("language_servers", "sensitive_never_export",
                    "config_to_export", "non_portable_markers", "security_flags"):
            self.assertIn(key, cat)

    def test_lsp_entries_have_binary_and_install(self):
        cat = ce.load_catalog()
        for name, meta in cat["language_servers"].items():
            self.assertIn("binary", meta, f"{name} sem binary")
            self.assertIn("install", meta, f"{name} sem install")
            self.assertIn("for_plugins", meta, f"{name} sem for_plugins")

    def test_global_claude_md_exported_local_blindado(self):
        # CLAUDE.md global é exportável; CLAUDE.local.md (pessoal) nunca viaja.
        cat = ce.load_catalog()
        self.assertIn("CLAUDE.md", cat["config_to_export"]["files"])
        self.assertIn("CLAUDE.local.md", cat["sensitive_never_export"]["files"])


class TestSanitize(unittest.TestCase):
    def test_removes_secret_keys(self):
        settings = {
            "env": {"API_KEY": "xyz", "GITHUB_TOKEN": "ghp_x", "EDITOR": "micro"},
            "my_secret": "s",
            "theme": "auto",
        }
        cleaned, removed = ce.sanitize_settings(settings)
        self.assertNotIn("my_secret", cleaned)
        self.assertNotIn("API_KEY", cleaned["env"])
        self.assertNotIn("GITHUB_TOKEN", cleaned["env"])
        self.assertIn("EDITOR", cleaned["env"])       # não-segredo permanece
        self.assertEqual(cleaned["theme"], "auto")
        self.assertTrue(any("my_secret" in r for r in removed))

    def test_home_path_generalized(self):
        cmd = f"bash {ce.HOME_STR}/.claude/statusline-command.sh"
        settings = {"statusLine": {"command": cmd}}
        cleaned, _ = ce.sanitize_settings(settings)
        self.assertIn("${HOME}", cleaned["statusLine"]["command"])
        # O home absoluto não pode sobrar em lugar nenhum.
        self.assertNotIn(ce.HOME_STR, json.dumps(cleaned))

    def test_nested_secrets_in_lists(self):
        settings = {"items": [{"token": "abc", "name": "ok"}]}
        cleaned, _ = ce.sanitize_settings(settings)
        self.assertNotIn("token", cleaned["items"][0])
        self.assertIn("name", cleaned["items"][0])


class TestDetectLanguageServers(unittest.TestCase):
    def test_only_enabled_plugins_count(self):
        cat = ce.load_catalog()
        enabled = {
            "typescript-lsp@claude-plugins-official": True,
            "gopls-lsp@claude-plugins-official": False,   # desabilitado
        }
        with mock.patch.object(ce, "which",
                               side_effect=lambda b: f"/x/{b}" if b == "typescript-language-server" else None):
            lsp = ce.detect_language_servers(cat, enabled)
        names = {l["language_server"] for l in lsp}
        self.assertIn("typescript-language-server", names)   # plugin TS ligado
        self.assertNotIn("gopls", names)                     # gopls desligado
        ts = next(l for l in lsp if l["language_server"] == "typescript-language-server")
        self.assertTrue(ts["installed_on_source"])
        self.assertEqual(ts["for_plugins"], ["typescript-lsp@claude-plugins-official"])

    def test_missing_binary_flagged(self):
        cat = ce.load_catalog()
        enabled = {"rust-analyzer-lsp@claude-plugins-official": True}
        with mock.patch.object(ce, "which", return_value=None):
            lsp = ce.detect_language_servers(cat, enabled)
        ra = next(l for l in lsp if l["language_server"] == "rust-analyzer")
        self.assertFalse(ra["installed_on_source"])


class TestNonPortableAndSecurity(unittest.TestCase):
    def test_detects_wsl_marker(self):
        cat = ce.load_catalog()
        settings = {"hooks": {"S": [{"command": "wsl-screenshot-cli start --daemon"}]}}
        self.assertIn("wsl-screenshot-cli", ce.scan_non_portable(settings, cat))

    def test_detects_macos_marker(self):
        # Fluxo reverso: hooks macOS num settings de origem Mac devem ser marcados.
        cat = ce.load_catalog()
        settings = {"hooks": {"S": [{"command": "osascript -e 'display notification'"}]},
                    "statusLine": {"command": "/opt/homebrew/bin/foo"}}
        hits = ce.scan_non_portable(settings, cat)
        self.assertIn("osascript", hits)
        self.assertIn("/opt/homebrew", hits)

    def test_finds_security_flags(self):
        cat = ce.load_catalog()
        settings = {"permissions": {"defaultMode": "bypassPermissions"},
                    "skipAutoPermissionPrompt": True}
        flags = ce.find_security_flags(settings, cat)
        self.assertEqual(flags["permissions.defaultMode"], "bypassPermissions")
        self.assertTrue(flags["skipAutoPermissionPrompt"])

    def test_absent_flags_not_reported(self):
        cat = ce.load_catalog()
        flags = ce.find_security_flags({"theme": "auto"}, cat)
        self.assertEqual(flags, {})


class TestManifestAndSetup(unittest.TestCase):
    def _manifest(self):
        settings = {
            "enabledPlugins": {"typescript-lsp@claude-plugins-official": True,
                               "caveman@caveman": False},
        }
        plugins_data = {"plugins": {
            "typescript-lsp@claude-plugins-official": [{"version": "1.0.0"}],
            "caveman@caveman": [{"version": "x", "gitCommitSha": "abc"}],
        }}
        marketplaces = {"caveman": {"source": {"source": "github", "repo": "JuliusBrussee/caveman"}}}
        lsp = [{"language_server": "typescript-language-server",
                "binary": "typescript-language-server",
                "for_plugins": ["typescript-lsp@claude-plugins-official"],
                "describe": "TS", "installed_on_source": True,
                "source_path": "/x", "install": {"pnpm": "pnpm add -g x"}}]
        node = {"pnpm": ["typescript@6.0.3"], "npm": []}
        return ce.build_manifest(settings, plugins_data, marketplaces, lsp, node,
                                 ["wsl-screenshot-cli"],
                                 {"permissions.defaultMode": "bypassPermissions"},
                                 ["my_secret"], ["settings.json"])

    def test_manifest_keys(self):
        m = self._manifest()
        for k in ("marketplaces", "plugins", "language_servers",
                  "global_node_packages", "security_flags",
                  "non_portable_markers_found", "secrets_removed_from_settings"):
            self.assertIn(k, m)

    def test_plugin_enabled_flag(self):
        m = self._manifest()
        caveman = next(p for p in m["plugins"] if p["name"] == "caveman@caveman")
        self.assertFalse(caveman["enabled"])

    def test_setup_md_has_phases_and_warnings(self):
        md = ce.render_setup_md(self._manifest())
        for marker in ("## Fase 1 — Marketplaces", "## Fase 3 — Language servers",
                       "## Fase 6 — Verificação", "bypassPermissions",
                       "wsl-screenshot-cli", "claude plugin marketplace add"):
            self.assertIn(marker, md)

    def test_setup_md_offers_pnpm_and_npm(self):
        # Máquina alvo pode ter só npm: o roteiro precisa oferecer os dois.
        md = ce.render_setup_md(self._manifest())
        self.assertIn("pnpm add -g", md)
        self.assertIn("npm install -g", md)
        self.assertIn("prefira `pnpm`", md)

    def test_setup_md_reinforces_idempotence(self):
        md = ce.render_setup_md(self._manifest())
        self.assertIn("command -v", md)                       # checagem antes de instalar
        self.assertIn("claude plugin marketplace list", md)   # idempotência de marketplace
        self.assertIn("claude plugin list", md)               # idempotência de plugin


class TestCopyTextSanitized(unittest.TestCase):
    def test_replaces_home_in_file(self):
        tmp = Path(tempfile.mkdtemp())
        src = tmp / "in.sh"
        src.write_text(f"echo {ce.HOME_STR}/.claude\n", encoding="utf-8")
        dst = tmp / "out" / "in.sh"
        ce.copy_text_sanitized(src, dst)
        out = dst.read_text(encoding="utf-8")
        self.assertIn("${HOME}", out)
        self.assertNotIn(ce.HOME_STR, out)


class TestCopyClaudeConfig(unittest.TestCase):
    def test_global_claude_md_copiado_local_ignorado(self):
        # ~/.claude fake: CLAUDE.md (exporta) + CLAUDE.local.md (não deve viajar).
        cat = ce.load_catalog()
        tmp = Path(tempfile.mkdtemp())
        fake = tmp / ".claude"
        (fake).mkdir()
        (fake / "CLAUDE.md").write_text("# instruções globais\n", encoding="utf-8")
        (fake / "CLAUDE.local.md").write_text("# pessoal — não compartilhar\n", encoding="utf-8")
        out = tmp / "out"
        with mock.patch.object(ce, "CLAUDE_DIR", fake), \
             mock.patch.object(ce, "OUT", out), \
             mock.patch.object(ce, "CONFIG_OUT", out / "config"):
            copied = ce.copy_claude_config(cat, {"theme": "auto"})
        self.assertIn("CLAUDE.md", copied)
        self.assertTrue((out / "config" / "CLAUDE.md").exists())
        self.assertFalse((out / "config" / "CLAUDE.local.md").exists())  # blindado


if __name__ == "__main__":
    unittest.main(verbosity=2)
