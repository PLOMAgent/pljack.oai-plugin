import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("screensaver_text", Path(__file__).with_name("screensaver_text.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ScreensaverTextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.config = self.base / "screensaver-text.json"
        self.branding = self.base / "branding/screensaver.txt"
        self.shell = self.base / "shell.json"
        self.original = {"version": 1, "idle": {"screensaver": 150, "lock": 1200},
                         "bar": {"layout": {"right": [{"id": "example"}]}}}
        self.shell.write_text(json.dumps(self.original))

    def test_current_text_follows_default_logo_even_with_stale_saved_text(self):
        logo = self.base / "logo.txt"
        logo.write_text("stock art")
        self.branding.parent.mkdir()
        self.branding.write_text("stock art")
        self.config.write_text('{"text":"old custom"}')
        self.assertEqual(module.read_current_text(self.config, self.branding, logo), "Omarchy")

    def test_current_text_reads_saved_custom_text_when_artwork_is_not_default(self):
        logo = self.base / "logo.txt"
        logo.write_text("stock art")
        self.branding.parent.mkdir()
        self.branding.write_text("custom art")
        self.config.write_text('{"text":"My custom text"}')
        self.assertEqual(module.read_current_text(self.config, self.branding, logo), "My custom text")

    def test_plugin_identity_and_helper_paths_match_renamed_install(self):
        folder = Path(__file__).parent
        manifest = json.loads((folder / "manifest.json").read_text())
        bar = (folder / "BarWidget.qml").read_text()
        panel = (folder / "Panel.qml").read_text()
        self.assertEqual(manifest["id"], "pljack.oai-plugin")
        self.assertIn('moduleName: "pljack.oai-plugin"', bar)
        self.assertIn('moduleName: "pljack.oai-plugin"', panel)
        self.assertIn('ipcTarget: "pljack.oai-plugin"', panel)
        self.assertIn('/plugins/pljack.oai-plugin/screensaver_text.py', panel)
        self.assertNotIn('pljack.oai-plugin-test', bar + panel + json.dumps(manifest))

    def test_timeout_minutes_label_updates_from_seconds(self):
        panel = Path(__file__).with_name("Panel.qml").read_text()
        start = panel.index("function minutesLabel(seconds)")
        end = panel.index("\n  }", start) + len("\n  }")
        js = panel[start:end] + "\nconsole.log([minutesLabel('150'), minutesLabel('15'), minutesLabel('60'), minutesLabel('')].join('|'))"
        labels = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout.strip()
        self.assertEqual(labels, "≈ 2.5 minutes|≈ 0.25 minutes|≈ 1 minute|")
        self.assertLess(panel.index("minutesLabel(root.secondsText)"), panel.index("text: root.errorMessage"))

    def test_bundled_font_renders_artwork_without_system_font(self):
        with patch.object(module.shutil, "which", return_value="/usr/bin/figlet"):
            module.save("Test", self.config, self.branding, self.shell, "240", launch=False)
        self.assertIn("█", self.branding.read_text())
        self.assertEqual(json.loads(self.config.read_text())["text"], "Test")

    def test_missing_bundled_font_reports_plugin_install_problem(self):
        with patch.object(module.shutil, "which", return_value="/usr/bin/figlet"), \
             patch.object(module, "FONT_PATH", self.base / "missing.flf"):
            with self.assertRaises(module.MissingFont) as caught:
                module.save("hello", self.config, self.branding, self.shell, "240", launch=False)
        self.assertIn("plugin", str(caught.exception).lower())
        self.assertNotIn("pkg add figlet", str(caught.exception))
        self.assertFalse(self.config.exists())
        self.assertFalse(self.branding.exists())

    def test_missing_figlet_reports_install_command_without_changing_files(self):
        with patch.object(module.shutil, "which", return_value=None):
            with self.assertRaises(module.MissingFiglet) as caught:
                module.save("hello", self.config, self.branding, self.shell, "240", launch=False)
        self.assertIn("omarchy pkg add figlet", str(caught.exception))
        self.assertFalse(self.config.exists())
        self.assertFalse(self.branding.exists())
        self.assertEqual(json.loads(self.shell.read_text()), self.original)

    def test_panel_checks_dependency_on_open_and_reports_it_on_save(self):
        panel = Path(__file__).with_name("Panel.qml").read_text()
        self.assertIn("dependencyProcess.running = true", panel)
        self.assertIn('"--check-figlet"', panel)
        self.assertIn("if (exitCode === 3)", panel)
        self.assertIn("if (exitCode === 4)", panel)
        self.assertIn("Bundled screensaver font", panel)
        self.assertIn("omarchy pkg add figlet", panel)
        self.assertIn("wrapMode: Text.WordWrap", panel[panel.index('text: root.errorMessage'):])

    def test_check_figlet_cli_exits_with_distinct_status(self):
        with patch.object(module.sys, "argv", ["screensaver_text.py", "--check-figlet"]), \
             patch.object(module.shutil, "which", return_value=None), \
             patch("sys.stderr") as stderr:
            self.assertEqual(module.main(), 3)
            self.assertIn("omarchy pkg add figlet", str(stderr.write.call_args_list))

    @unittest.skipUnless(shutil.which("figlet"), "requires figlet and ansi-regular font")
    def test_save_preserves_unrelated_shell_config_and_artwork(self):
        text = "It's $HOME; wow!"
        module.save(text, self.config, self.branding, self.shell, "240", launch=False)
        self.assertEqual(json.loads(self.config.read_text())["text"], text)
        self.assertIn("█", self.branding.read_text())
        expected = self.original.copy()
        expected["idle"] = {"screensaver": 240, "lock": 1200}
        self.assertEqual(json.loads(self.shell.read_text()), expected)
        self.assertEqual(module.read_timeouts(self.shell), (240, 1200))

    def test_invalid_seconds_do_not_touch_any_files(self):
        for value in ("", "abc", "1.5", "-1", "０２", "0", "1200", "86401"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    module.save("hello", self.config, self.branding, self.shell, value, launch=False)
                self.assertFalse(self.config.exists())
                self.assertFalse(self.branding.exists())
                self.assertEqual(json.loads(self.shell.read_text()), self.original)

    @unittest.skipUnless(shutil.which("figlet"), "requires figlet and ansi-regular font")
    def test_save_schedules_shell_restart_after_timeout_change(self):
        real_run = subprocess.run
        seen = []

        def run(command, *args, **kwargs):
            seen.append(command)
            if command[0] == "figlet":
                return real_run(command, *args, **kwargs)
            return subprocess.CompletedProcess(command, 0)

        with patch.object(module.subprocess, "run", side_effect=run):
            module.save("hello", self.config, self.branding, self.shell, "15")
        self.assertEqual(json.loads(self.shell.read_text())["idle"]["screensaver"], 15)
        self.assertIn(["systemd-run", "--user", "--collect", "--on-active=2s",
                       module.shutil.which("omarchy"), "restart", "shell"], seen)
        self.assertIn(["omarchy-launch-screensaver", "force"], seen)

    def test_uninstall_is_delayed_and_targets_only_this_plugin(self):
        with patch.object(module.subprocess, "run") as run:
            module.schedule_uninstall()
        run.assert_called_once_with(
            ["systemd-run", "--user", "--collect", "--on-active=2s",
             module.sys.executable, str(Path(module.__file__).resolve()), "--perform-uninstall"],
            check=True,
        )
        self.assertTrue(self.shell.exists())
        self.assertEqual(json.loads(self.shell.read_text()), self.original)

    def test_uninstall_restores_defaults_then_removes_and_restarts_shell(self):
        config_dir = self.base / ".config/omarchy"
        config_dir.mkdir(parents=True)
        self.config = config_dir / "screensaver-text.json"
        self.branding = config_dir / "branding/screensaver.txt"
        self.shell = config_dir / "shell.json"
        logo = self.base / "logo.txt"
        logo.write_bytes(b"stock logo\n")
        self.branding.parent.mkdir()
        self.branding.write_bytes(b"custom art\n")
        self.config.write_text('{"text":"custom"}')
        self.original["idle"]["screensaver"] = 60
        self.shell.write_text(json.dumps(self.original))
        with patch.object(module.Path, "home", return_value=self.base), \
             patch.dict(module.os.environ, {"OMARCHY_PATH": str(self.base)}), \
             patch.object(module.subprocess, "run") as run:
            module.perform_uninstall()
        self.assertEqual(self.branding.read_bytes(), logo.read_bytes())
        self.assertFalse(self.config.exists())
        actual = json.loads(self.shell.read_text())
        self.assertEqual(actual["idle"], {"screensaver": 150, "lock": 1200})
        self.assertEqual(actual["bar"], self.original["bar"])
        self.assertEqual([call.args[0] for call in run.call_args_list], [
            [module.shutil.which("omarchy"), "plugin", "remove", "pljack.oai-plugin", "--yes"],
            [module.shutil.which("omarchy"), "restart", "shell"],
        ])
        self.assertTrue(all(call.kwargs.get("check") for call in run.call_args_list))

    def test_uninstall_restores_logo_if_branding_folder_is_missing(self):
        config_dir = self.base / ".config/omarchy"
        config_dir.mkdir(parents=True)
        (self.base / "logo.txt").write_bytes(b"stock logo\n")
        (config_dir / "shell.json").write_text(json.dumps(self.original))
        with patch.object(module.Path, "home", return_value=self.base), \
             patch.dict(module.os.environ, {"OMARCHY_PATH": str(self.base)}), \
             patch.object(module.subprocess, "run") as run:
            module.perform_uninstall()
        self.assertEqual((config_dir / "branding/screensaver.txt").read_bytes(), b"stock logo\n")
        self.assertEqual(len(run.call_args_list), 2)

    def test_scheduled_uninstall_cli_dispatches_without_requiring_config(self):
        with patch.object(module.sys, "argv", ["screensaver_text.py", "--perform-uninstall"]), \
             patch.object(module, "perform_uninstall") as perform:
            self.assertEqual(module.main(), 0)
        perform.assert_called_once_with()

    def test_uninstall_control_requires_confirmation_and_reports_errors(self):
        panel = Path(__file__).with_name("Panel.qml").read_text()
        self.assertLess(panel.index('text: "Uninstall"'), panel.index('text: root.editText'))
        self.assertIn('text: "Uninstall restores stock artwork and the 150-second timeout."', panel)
        self.assertIn('text: "Reset & remove?"', panel)
        self.assertIn('onClicked: root.confirmUninstall = true', panel)
        self.assertIn('onClicked: root.scheduleUninstall()', panel)
        self.assertIn('onClicked: root.confirmUninstall = false', panel)
        self.assertIn('"--uninstall"', panel)
        self.assertIn('root.errorMessage = "Could not schedule plugin uninstall."', panel)

    def test_empty_text_does_not_touch_any_files(self):
        with self.assertRaises(ValueError):
            module.save("   ", self.config, self.branding, self.shell, "240", launch=False)
        self.assertFalse(self.config.exists())
        self.assertFalse(self.branding.exists())
        self.assertEqual(json.loads(self.shell.read_text()), self.original)

    def test_restore_uses_official_command_then_clears_old_input(self):
        self.config.write_text('{"text":"custom"}')
        with patch.object(module.subprocess, "run") as run:
            module.restore_default(self.config, self.shell)
        run.assert_called_once_with(["omarchy", "branding", "screensaver", "reset"], check=True)
        self.assertFalse(self.config.exists())
        self.assertEqual(json.loads(self.shell.read_text()), self.original)

    def test_restore_resets_timeout_to_150_and_schedules_live_reload(self):
        self.original["idle"]["screensaver"] = 60
        self.shell.write_text(json.dumps(self.original))
        self.config.write_text('{"text":"custom"}')
        with patch.object(module.subprocess, "run") as run:
            module.restore_default(self.config, self.shell)
        actual = json.loads(self.shell.read_text())
        self.assertEqual(actual["idle"], {"screensaver": 150, "lock": 1200})
        self.assertEqual(actual["bar"], self.original["bar"])
        self.assertFalse(self.config.exists())
        self.assertEqual(run.call_args_list[0].args[0], ["omarchy", "branding", "screensaver", "reset"])
        self.assertTrue(any(call.args[0][0] == "systemd-run" for call in run.call_args_list))

    def test_failed_restore_preserves_old_input(self):
        self.config.write_text('{"text":"custom"}')
        with patch.object(module.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "omarchy")):
            with self.assertRaises(subprocess.CalledProcessError):
                module.restore_default(self.config, self.shell)
        self.assertTrue(self.config.exists())


if __name__ == "__main__":
    unittest.main()
