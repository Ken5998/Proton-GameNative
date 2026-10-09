"""Offline checks of the Box64 route installer against a fake Steam home."""
from pathlib import Path
import os
import shutil
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BOX64 = ROOT / 'box64'


class Box64InstallerTests(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.home)
        self.env = dict(os.environ, HOME=str(self.home))
        # A stand-in Box64 that only answers --version.
        self.bundle = self.home / 'box64-armada.tar.gz'
        staging = self.home / 'staging' / 'box64-armada'
        staging.mkdir(parents=True)
        (staging / 'box64').write_text('#!/bin/sh\necho "Box64 test build"\n')
        (staging / 'box64').chmod(0o755)
        with tarfile.open(self.bundle, 'w:gz') as tar:
            tar.add(staging, arcname='box64-armada')
        self.tools = self.home / '.local/share/Steam/compatibilitytools.d'

    def fake_proton(self, name, wow64=True):
        src = self.tools / name
        (src / 'files' / 'bin-wow64').mkdir(parents=True)
        (src / 'files' / 'lib').mkdir()
        (src / 'proton').write_text('#!/usr/bin/env python3\n# PROTON_USE_WOW64\n' if wow64 else '#!/usr/bin/env python3\n')
        shutil.copy('/bin/true', src / 'files' / 'bin-wow64' / 'wine')
        (src / 'files' / 'bin-wow64' / 'notes.txt').write_text('not an ELF\n')
        (src / 'toolmanifest.vdf').write_text('"manifest"\n{\n  "require_tool_appid" "1628350"\n  "commandline" "/proton %verb%"\n}\n')
        (src / 'compatibilitytool.vdf').write_text('"compatibilitytools" {}\n')
        (src / 'version').write_text('1 test\n')
        return src

    def run_script(self, *args, ok=True):
        env = dict(self.env, BUNDLE=str(self.bundle))
        result = subprocess.run(['bash', str(BOX64 / 'armada-box64.sh'), *args], env=env, text=True, capture_output=True)
        if ok and result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        return result

    def test_install_wraps_binaries_and_sets_defaults(self):
        src = self.fake_proton('GE-Test 10')
        out = self.run_script('install', 'GE-Test 10').stdout
        self.assertIn('GE-Test 10 (Box64 WoW64)', out)
        dst = self.tools / 'GE-Test-10-box64-wow64'
        wrapper = (dst / 'proton').read_text()
        for line in ('export PROTON_USE_WOW64="${PROTON_USE_WOW64:-1}"',
                     'export PROTON_NO_NTSYNC="${PROTON_NO_NTSYNC:-1}"',
                     'export BOX64_DYNACACHE="${BOX64_DYNACACHE:-0}"', 'unset HODLL'):
            self.assertIn(line, wrapper)
        wine = (dst / 'files' / 'bin-wow64' / 'wine').read_text()
        self.assertIn(str(self.home / '.local/share/box64-armada/box64'), wine)
        self.assertTrue((dst / 'files' / 'bin-wow64' / 'notes.txt').is_symlink())
        self.assertEqual(os.readlink(dst / 'files' / 'lib'), str(src / 'files' / 'lib'))
        self.assertNotIn('require_tool_appid', (dst / 'toolmanifest.vdf').read_text())
        self.assertIn('Box64 test build', self.run_script('status').stdout)
        # Reinstalling replaces its own tool; the original Proton stays untouched.
        self.run_script('install', 'GE-Test 10')
        self.assertEqual((src / 'proton').read_text(), '#!/usr/bin/env python3\n# PROTON_USE_WOW64\n')
        self.assertTrue((src / 'files' / 'bin-wow64' / 'wine').read_bytes().startswith(b'\x7fELF'))

    def test_classic_fallback_and_refusals(self):
        self.fake_proton('Old', wow64=False)
        out = self.run_script('install', 'Old').stdout
        self.assertIn('classic 32-bit mode', out)
        self.assertNotIn('PROTON_USE_WOW64', (self.tools / 'Old-box64' / 'proton').read_text())
        foreign = self.tools / 'Mine-box64'
        foreign.mkdir()
        self.fake_proton('Mine')
        self.assertNotEqual(self.run_script('install', 'Mine', 'classic', ok=False).returncode, 0)
        self.assertTrue(foreign.is_dir())
        for bad in (['install'], ['install', 'x;id'], ['install', 'Old', 'other'], ['cleanprefix', '../x'], ['bogus']):
            self.assertNotEqual(self.run_script(*bad, ok=False).returncode, 0, bad)

    def test_cleanprefix_moves_arm64_leftovers(self):
        pfx = self.home / '.local/share/Steam/steamapps/compatdata/123/pfx'
        sys32 = pfx / 'drive_c/windows/system32'
        sys32.mkdir(parents=True)
        pe = bytearray(512)
        pe[0:2] = b'MZ'
        pe[0x3c:0x40] = (0x80).to_bytes(4, 'little')
        pe[0x80:0x84] = b'PE\0\0'
        pe[0x84:0x86] = (0xaa64).to_bytes(2, 'little')
        (sys32 / 'wowbox64.dll').write_bytes(bytes(pe))
        pe[0x84:0x86] = (0x8664).to_bytes(2, 'little')
        (sys32 / 'ntdll.dll').write_bytes(bytes(pe))
        (pfx / 'system.reg').write_text('[Software\\\\Microsoft\\\\Wow64\\\\x86] 1\n@="libwow64fex.dll"\n\n'
                                        '[Software\\\\Wine] 1\n"Keep"="1"\n')
        out = self.run_script('cleanprefix', '123').stdout
        self.assertIn('Moved system32/wowbox64.dll (ARM64)', out)
        self.assertTrue((sys32 / 'ntdll.dll').exists())
        self.assertFalse((sys32 / 'wowbox64.dll').exists())
        reg = (pfx / 'system.reg').read_text()
        self.assertNotIn('Wow64', reg)
        self.assertIn('"Keep"="1"', reg)
        self.assertEqual(len(list(pfx.glob('arm64-leftovers-*/system32/wowbox64.dll'))), 1)

    def test_uninstall_removes_only_own_tools(self):
        self.fake_proton('GE-Test')
        self.run_script('install', 'GE-Test')
        self.run_script('uninstall')
        self.assertFalse((self.tools / 'GE-Test-box64-wow64').exists())
        self.assertTrue((self.tools / 'GE-Test' / 'proton').exists())
        self.assertFalse((self.home / '.local/share/box64-armada').exists())


if __name__ == '__main__':
    unittest.main()
