import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
import chrome_beta as B  # noqa: E402


class TestChromeBeta(unittest.TestCase):
    def test_port_and_paths_are_agents_own(self):
        self.assertEqual(B.PORT, 9290)
        self.assertTrue(str(B.PROFILE).endswith("data/agents/browser_profiles/chrome_beta"))
        self.assertTrue(str(B.STATE).endswith("data/agents/state/chrome_beta.json"))

    def test_stable_refused(self):
        with self.assertRaises(RuntimeError):
            B.ensure_running("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")

    def test_alive_but_not_ours_refused(self):
        with mock.patch.object(B, "cdp_alive", return_value=True), \
             mock.patch.object(B, "_read_state", return_value={}), \
             mock.patch.object(B.os.path, "exists", return_value=True), \
             mock.patch.object(B.subprocess, "run", return_value=mock.Mock(stdout=B.BUNDLE_ID + "\n")):
            with self.assertRaisesRegex(RuntimeError, "BETA_PORT_NOT_OWNED"):
                B.ensure_running()

    def test_alive_and_ours_returns_url(self):
        with mock.patch.object(B, "cdp_alive", return_value=True), \
             mock.patch.object(B, "_read_state", return_value={"pid": 5}), \
             mock.patch.object(B, "owns", return_value=True), \
             mock.patch.object(B.os.path, "exists", return_value=True), \
             mock.patch.object(B.subprocess, "run", return_value=mock.Mock(stdout=B.BUNDLE_ID + "\n")):
            self.assertEqual(B.ensure_running(), "http://127.0.0.1:9290")

    def test_owns_checks_profile_and_port(self):
        cmd = f"{B.EXECUTABLE} --user-data-dir={B.PROFILE} --remote-debugging-port=9290"
        with mock.patch.object(B, "_command", return_value=cmd):
            self.assertTrue(B.owns(99))
        with mock.patch.object(B, "_command", return_value=cmd.replace("9290", "9240")):
            self.assertFalse(B.owns(99))


if __name__ == "__main__":
    unittest.main()
