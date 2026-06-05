#!/usr/bin/env python3
"""
Testes de regressão para lib/exporter.py.

Rodar:  python3 tests/test_exporter.py        (ou:  python3 -m unittest -v tests.test_exporter)

Cobre as funções puras (parse_zshrc, scan_platform_lines, build_manifest,
render_setup_md) e as que tocam o sistema (detect_tools, copy_dotfiles,
detect_os, is_wsl), isolando o I/O com mocks e diretórios temporários.
Sem dependências externas — só a stdlib.
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# Torna lib/exporter.py importável.
LIB = Path(__file__).resolve().parent.parent / "lib"
sys.path.insert(0, str(LIB))
import exporter  # type: ignore  # noqa: E402  (resolvido via sys.path acima)


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class TestLoadCatalog(unittest.TestCase):
    def test_catalog_has_core_sections(self):
        cat = exporter.load_catalog()
        for key in ("cli_tools", "omz_plugins", "omz_themes",
                    "frameworks", "version_managers", "platform_specific_patterns"):
            self.assertIn(key, cat)

    def test_every_cli_tool_has_detect_verify_install(self):
        cat = exporter.load_catalog()
        for name, meta in cat["cli_tools"].items():
            self.assertIn("detect", meta, f"{name} sem 'detect'")
            self.assertIn("verify", meta, f"{name} sem 'verify'")
            self.assertIn("install", meta, f"{name} sem 'install'")


class TestParseZshrc(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_extracts_theme_plugins_framework(self):
        zshrc = write(self.tmp / ".zshrc", (
            'export ZSH="$HOME/.oh-my-zsh"\n'
            '# ZSH_THEME="spaceship"\n'          # comentado: deve ser ignorado
            'ZSH_THEME="dracula-pro"\n'
            'plugins=(git zsh-completions zsh-autosuggestions)\n'
            'source "$ZSH/oh-my-zsh.sh"\n'
        ))
        info = exporter.parse_zshrc(zshrc)
        self.assertEqual(info["theme"], "dracula-pro")
        self.assertEqual(info["framework"], "oh-my-zsh")
        self.assertEqual(info["plugins"], ["git", "zsh-completions", "zsh-autosuggestions"])

    def test_plugins_multiline(self):
        zshrc = write(self.tmp / ".zshrc", (
            'plugins=(\n  git\n  zsh-syntax-highlighting\n)\n'
        ))
        info = exporter.parse_zshrc(zshrc)
        self.assertEqual(info["plugins"], ["git", "zsh-syntax-highlighting"])

    def test_missing_file_returns_empty(self):
        info = exporter.parse_zshrc(self.tmp / "naoexiste")
        self.assertIsNone(info["theme"])
        self.assertEqual(info["plugins"], [])


class TestScanPlatformLines(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.catalog = exporter.load_catalog()

    def test_detects_wsl_and_rename_aliases(self):
        zshrc = write(self.tmp / ".zshrc", (
            'alias ll="eza -la"\n'                 # portável: NÃO deve aparecer
            'alias bat="batcat"\n'                 # rename Debian: deve aparecer
            'export PULSE_SERVER=unix:/mnt/wslg/x\n'  # WSL: deve aparecer
            'VSCODE_BIN="/mnt/c/Users/x"\n'        # WSL: deve aparecer
        ))
        hits = exporter.scan_platform_lines(zshrc, self.catalog)
        texts = [h["text"] for h in hits]
        self.assertTrue(any("batcat" in t for t in texts))
        self.assertTrue(any("/mnt/wslg" in t for t in texts))
        self.assertTrue(any("/mnt/c" in t for t in texts))
        self.assertFalse(any('alias ll="eza -la"' == t for t in texts))

    def test_each_hit_has_line_and_pattern(self):
        zshrc = write(self.tmp / ".zshrc", 'export MESA_D3D12_X=1\n')
        hits = exporter.scan_platform_lines(zshrc, self.catalog)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["line"], 1)
        self.assertIn("MESA_D3D12", hits[0]["pattern"])

    def test_detects_macos_lines_bidirectional(self):
        # Fluxo reverso: origem macOS → estas linhas devem ser marcadas.
        zshrc = write(self.tmp / ".zshrc", (
            'eval "$(/opt/homebrew/bin/brew shellenv)"\n'
            'alias copy="pbcopy"\n'
            'alias ls="ls -G"\n'
            'export EDITOR=micro\n'           # portável: NÃO deve aparecer
        ))
        hits = exporter.scan_platform_lines(zshrc, self.catalog)
        texts = [h["text"] for h in hits]
        self.assertTrue(any("/opt/homebrew" in t for t in texts))
        self.assertTrue(any("pbcopy" in t for t in texts))
        self.assertFalse(any("EDITOR=micro" in t for t in texts))

    def test_wsl_path_with_users_not_misclassified_as_macos(self):
        # "/mnt/c/Users/..." contém "/Users/" (marcador macOS) mas é WSL puro.
        zshrc = write(self.tmp / ".zshrc",
                      'VSCODE_BIN="/mnt/c/Users/ike/AppData/Local/bin"\n')
        hits = exporter.scan_platform_lines(zshrc, self.catalog)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["platform"], "wsl_windows")

    def test_hit_has_platform_label(self):
        zshrc = write(self.tmp / ".zshrc", (
            'export PULSE_SERVER=/mnt/wslg/x\n'   # wsl_windows
            'alias copy="pbcopy"\n'               # macos
        ))
        hits = exporter.scan_platform_lines(zshrc, self.catalog)
        plats = {h["platform"] for h in hits}
        self.assertIn("wsl_windows", plats)
        self.assertIn("macos", plats)


class TestDetectTools(unittest.TestCase):
    def test_detects_only_present_binaries(self):
        catalog = exporter.load_catalog()
        # Finge que só zoxide e fzf existem.
        present = {"zoxide": "/usr/bin/zoxide", "fzf": "/usr/bin/fzf"}
        with mock.patch.object(exporter, "which", side_effect=lambda n: present.get(n)):
            detected = exporter.detect_tools(catalog)
        self.assertIn("zoxide", detected["cli_tools"])
        self.assertIn("fzf", detected["cli_tools"])
        self.assertNotIn("glow", detected["cli_tools"])

    def test_version_manager_detected_by_path(self):
        catalog = exporter.load_catalog()
        tmp = Path(tempfile.mkdtemp())
        fake_nvm = tmp / ".nvm"
        fake_nvm.mkdir()
        with mock.patch.object(exporter, "which", return_value=None), \
             mock.patch.object(exporter.os.path, "expanduser",
                               side_effect=lambda p: str(fake_nvm) if p == "~/.nvm" else p):
            detected = exporter.detect_tools(catalog)
        self.assertIn("nvm", detected["version_managers"])


class TestBuildManifest(unittest.TestCase):
    def _manifest(self):
        catalog = exporter.load_catalog()
        zsh_info = {
            "framework": "oh-my-zsh",
            "theme": "dracula-pro",
            "plugins": ["git", "zsh-autosuggestions"],
        }
        detected = {
            "cli_tools": {"zoxide": {"path": "/usr/bin/zoxide"}},
            "version_managers": {"nvm": {"path": "/home/x/.nvm"}},
            "frameworks": {"oh-my-zsh": {"path": "/home/x/.oh-my-zsh"}},
        }
        platform_lines = [{"line": 1, "pattern": "/mnt/c", "text": "x"}]
        return exporter.build_manifest(
            catalog, zsh_info, detected, platform_lines, [".zshrc"], "debian")

    def test_structure_keys(self):
        m = self._manifest()
        for key in ("generated_from", "framework", "theme", "omz_plugins",
                    "cli_tools", "version_managers", "dotfiles_copied",
                    "platform_specific_lines"):
            self.assertIn(key, m)

    def test_verify_is_propagated(self):
        m = self._manifest()
        zoxide = next(t for t in m["cli_tools"] if t["name"] == "zoxide")
        self.assertEqual(zoxide["verify"], "zoxide --version")

    def test_detect_fields_propagated(self):
        # detect/detect_alt/detect_path precisam ir ao manifest para o dry-run
        # reproduzir a mesma detecção do exporter (ex.: bat→batcat, nvm→~/.nvm).
        m = self._manifest()
        zoxide = next(t for t in m["cli_tools"] if t["name"] == "zoxide")
        self.assertEqual(zoxide["detect"], "zoxide")
        nvm = next(t for t in m["version_managers"] if t["name"] == "nvm")
        self.assertEqual(nvm["detect_path"], "~/.nvm")

    def test_paid_theme_flagged_manual(self):
        m = self._manifest()
        self.assertEqual(m["theme"]["name"], "dracula-pro")
        self.assertTrue(m["theme"]["manual"])
        self.assertTrue(m["theme"]["known"])

    def test_unknown_plugin_marked(self):
        catalog = exporter.load_catalog()
        zsh_info = {"framework": "oh-my-zsh", "theme": None,
                    "plugins": ["plugin-inexistente-xyz"]}
        detected = {"cli_tools": {}, "version_managers": {}, "frameworks": {}}
        m = exporter.build_manifest(catalog, zsh_info, detected, [], [], "macos")
        self.assertFalse(m["omz_plugins"][0]["known"])


class TestRenderSetupMd(unittest.TestCase):
    def setUp(self):
        catalog = exporter.load_catalog()
        zsh_info = {"framework": "oh-my-zsh", "theme": "dracula-pro",
                    "plugins": ["git"]}
        detected = {
            "cli_tools": {"zoxide": {"path": "/usr/bin/zoxide"},
                          "glow": {"path": "/usr/bin/glow"}},
            "version_managers": {"nvm": {"path": "/home/x/.nvm"}},
            "frameworks": {},
        }
        self.manifest = exporter.build_manifest(
            catalog, zsh_info, detected, [], [], "debian")
        self.md = exporter.render_setup_md(self.manifest)

    def test_has_all_phases(self):
        for marker in ("### Fase 0", "### Fase 0.5", "### Fase 1",
                       "### Fase 6"):
            self.assertIn(marker, self.md)

    def test_mentions_backup_and_revert(self):
        self.assertIn("BACKUP OBRIGATÓRIO", self.md)
        self.assertIn("scripts/backup.sh", self.md)
        self.assertIn("## Reverter", self.md)
        self.assertIn("restore.sh", self.md)

    def test_mentions_zsh_install_when_missing(self):
        self.assertIn("command -v zsh", self.md)
        self.assertIn("install -y zsh", self.md)

    def test_verify_table_lists_tool_commands(self):
        # As ferramentas detectadas devem aparecer com seu comando de verify.
        self.assertIn("zoxide --version", self.md)
        self.assertIn("glow --version", self.md)

    def test_idempotence_principle_present(self):
        self.assertIn("Idempotência", self.md)


class TestCopyDotfiles(unittest.TestCase):
    def test_copies_files_and_config_dirs(self):
        tmp = Path(tempfile.mkdtemp())
        home = tmp / "home"
        write(home / ".zshrc", "rc")
        write(home / ".config" / "micro" / "settings.json", "{}")
        out = tmp / "out" / "dotfiles"
        with mock.patch.object(exporter, "HOME", home), \
             mock.patch.object(exporter, "DOTFILES_OUT", out):
            copied = exporter.copy_dotfiles()
        self.assertIn(".zshrc", copied)
        self.assertTrue((out / ".zshrc").exists())
        self.assertTrue(any("micro" in c for c in copied))
        self.assertTrue((out / "config" / "micro" / "settings.json").exists())

    def test_idempotent_rerun(self):
        tmp = Path(tempfile.mkdtemp())
        home = tmp / "home"
        write(home / ".zshrc", "rc")
        out = tmp / "out" / "dotfiles"
        with mock.patch.object(exporter, "HOME", home), \
             mock.patch.object(exporter, "DOTFILES_OUT", out):
            exporter.copy_dotfiles()
            copied = exporter.copy_dotfiles()  # segunda vez não deve falhar
        self.assertIn(".zshrc", copied)


class TestOsDetection(unittest.TestCase):
    def test_macos(self):
        with mock.patch.object(exporter.platform, "system", return_value="Darwin"):
            self.assertEqual(exporter.detect_os(), "macos")

    def test_debian_when_apt_present(self):
        with mock.patch.object(exporter.platform, "system", return_value="Linux"), \
             mock.patch.object(exporter.shutil, "which", return_value="/usr/bin/apt"):
            self.assertEqual(exporter.detect_os(), "debian")

    def test_linux_without_apt(self):
        with mock.patch.object(exporter.platform, "system", return_value="Linux"), \
             mock.patch.object(exporter.shutil, "which", return_value=None):
            self.assertEqual(exporter.detect_os(), "linux")

    def test_is_wsl_true(self):
        with mock.patch.object(exporter.platform, "release",
                               return_value="6.6.0-microsoft-standard-WSL2"):
            self.assertTrue(exporter.is_wsl())

    def test_is_wsl_false(self):
        with mock.patch.object(exporter.platform, "release",
                               return_value="6.6.0-generic"):
            self.assertFalse(exporter.is_wsl())


if __name__ == "__main__":
    unittest.main(verbosity=2)
