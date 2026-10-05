"""Fast offline checks of input handling, transactions, and distribution contents."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import struct
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'


def run(*args, cwd=ROOT, ok=True):
    result = subprocess.run([str(v) for v in args], cwd=cwd, text=True, capture_output=True)
    if ok and result.returncode:
        raise AssertionError(result.stdout + result.stderr)
    return result


class VersionTests(unittest.TestCase):
    def test_versions_and_explicit_override(self):
        for tag, override, expected in [
            ('proton-11.0-2-20260928', 'auto', '11.0-2'),
            ('proton-12.0-1-20270115', 'auto', '12.0-1'),
            ('proton-123.45-67-20280229', 'auto', '123.45-67'),
            ('future-wine-tag', '12.0-rc1', '12.0-rc1'),
        ]:
            self.assertEqual(run('bash', SCRIPTS / 'detect-version.sh', tag, override).stdout.strip(), expected)

    def test_invalid_and_shell_metacharacters(self):
        for tag in ['proton-11.0-2-20260230', 'proton-11.0-2-YYYYMMDD', '11.0-2',
                    'proton-11.0-2-20260928-extra', '-option', '../escape', 'x;echo BAD', 'x\nBAD=1', '$(id)', '`id`']:
            self.assertNotEqual(run('bash', SCRIPTS / 'detect-version.sh', tag, ok=False).returncode, 0, tag)
        for version in ['../x', '-x', '1/2', '1;id', '1$(id)', '1\nBAD=1', '1..2', '1' * 81]:
            self.assertNotEqual(run('bash', SCRIPTS / 'detect-version.sh', 'valid-tag', version, ok=False).returncode, 0, version)


class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.wine = self.base / 'wine'
        self.wine.mkdir()
        self.manifest = (SCRIPTS / 'patch-profiles/gamenative-fex-linux.txt').read_text().splitlines()

    def fixture(self, invalid=(), missing=(), markers=True):
        marker_files = {
            'dlls/ntdll/unix/virtual.c': 'WINEVMEMMAXSIZE MemoryWineLoadUnixLibByName\n',
            'dlls/wow64/virtual.c': 'MemoryWineLoadUnixLibByNameWow64\n',
            'dlls/wow64/syscall.c': 'Wow64SuspendLocalThread\n',
            'dlls/ntdll/ntdll_misc.h': 'arm64ec_suspend_point\n',
        }
        for path, value in marker_files.items():
            f = self.wine / path
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(value if markers else 'no marker\n')
        for i, path in enumerate(self.manifest):
            f = self.wine / f'fixture/{i}.c'
            f.parent.mkdir(exist_ok=True)
            f.write_text('original\n')
            if i in missing:
                continue
            patch = self.wine / path
            patch.parent.mkdir(parents=True, exist_ok=True)
            old = 'wrong-context' if i in invalid else 'original'
            patch.write_text(f'diff --git a/fixture/{i}.c b/fixture/{i}.c\n--- a/fixture/{i}.c\n+++ b/fixture/{i}.c\n@@ -1 +1 @@\n-{old}\n+patched\n')
        run('git', 'init', '-q', self.wine)
        run('git', 'add', '.', cwd=self.wine)
        run('git', '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'fixture', cwd=self.wine)

    def snapshot(self):
        return {str(f.relative_to(self.wine)): hashlib.sha256(f.read_bytes()).hexdigest()
                for f in self.wine.rglob('*') if f.is_file() and '.git' not in f.relative_to(self.wine).parts}

    def apply(self, *flags, ok=True):
        return run('bash', SCRIPTS / 'apply-gamenative-fex-linux.sh', *flags,
                   self.wine, self.base / 'logs', ok=ok)

    def test_check_only_and_success(self):
        self.fixture()
        before = self.snapshot()
        self.apply('--check-only')
        self.assertEqual(before, self.snapshot())
        self.assertFalse(run('git', 'status', '--porcelain', cwd=self.wine).stdout)
        self.apply()
        for i in range(len(self.manifest)):
            self.assertEqual((self.wine / f'fixture/{i}.c').read_text(), 'patched\n')
        self.assertFalse(run('git', 'diff', '--cached', cwd=self.wine).stdout)

    def test_reports_every_failure_and_keeps_tree_and_index(self):
        self.fixture(invalid=(1, 14), missing=(5,))
        before = self.snapshot()
        index = (self.wine / '.git/index').read_bytes()
        result = self.apply(ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(index, (self.wine / '.git/index').read_bytes())
        for i in (1, 5, 14):
            self.assertIn(self.manifest[i], result.stderr)

    def test_missing_runtime_marker_prevents_mutation(self):
        self.fixture(markers=False)
        before = self.snapshot()
        self.assertNotEqual(self.apply(ok=False).returncode, 0)
        self.assertEqual(before, self.snapshot())

    def test_dirty_checkout_is_preserved(self):
        self.fixture()
        (self.wine / 'fixture/0.c').write_text('user changes\n')
        before = self.snapshot()
        self.assertNotEqual(self.apply(ok=False).returncode, 0)
        self.assertEqual(before, self.snapshot())

    def test_writcopy_is_precise_and_ambiguous_input_fails(self):
        self.fixture()
        path = self.wine / 'dlls/ntdll/unix/virtual.c'
        body = '''static NTSTATUS map_image_into_view( void )
{
    map_pe_header( ptr );
    /* set the image protections */
    set_vprot( view, ptr, ROUND_SIZE( 0, header_size, align_mask ), VPROT_COMMITTED | VPROT_READ );
    for (i = 0; i < nt->FileHeader.NumberOfSections; i++) {}
}
'''
        unrelated = 'int unrelated = VPROT_COMMITTED | VPROT_READ;\n'
        path.write_text(body + unrelated)
        run('bash', SCRIPTS / 'apply-writcopy.sh', self.wine)
        self.assertTrue(path.read_text().endswith(unrelated))
        self.assertEqual(path.read_text().count('| VPROT_WRITECOPY'), 1)
        before = path.read_bytes()
        self.assertNotEqual(run('bash', SCRIPTS / 'apply-writcopy.sh', self.wine, ok=False).returncode, 0)
        self.assertEqual(path.read_bytes(), before)
        path.write_text(body + body)
        before = path.read_bytes()
        self.assertNotEqual(run('bash', SCRIPTS / 'apply-writcopy.sh', self.wine, ok=False).returncode, 0)
        self.assertEqual(path.read_bytes(), before)


class PackagingTests(unittest.TestCase):
    def test_archives_preserve_layout_licenses_symlinks_and_patched_source(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            wine, meta, redist = [base / v for v in ('wine', 'meta', 'redist')]
            for d in (wine, meta, redist):
                d.mkdir()
            (wine / 'COPYING.LIB').write_text('Original Wine license\n')
            (wine / 'configure.ac').write_text('AC_INIT\n')
            (wine / 'patched.c').write_text('actual patched input\n')
            (wine / '.git').mkdir()
            (wine / '.git/secret').write_text('excluded')
            name = 'Proton-GameNative-12.0-1-arm64'
            (meta / 'build-info.json').write_text(json.dumps({'Version': '12.0-1', 'Package name': name, 'Source date epoch': '1700000000'}))
            (meta / 'build-info.txt').write_text('Public provenance\n')
            sources, output = base / 'sources', base / 'out'
            common = ['--version', '12.0-1', '--metadata', meta]
            run('bash', SCRIPTS / 'package-build.sh', 'source', *common, '--tree', wine, '--output', sources)
            source = sources / (name + '-source.tar.gz')
            with tarfile.open(source) as tar:
                self.assertFalse(any('.git' in Path(n).parts for n in tar.getnames()))
                self.assertEqual(tar.extractfile(name + '-source/wine/patched.c').read(), b'actual patched input\n')
                self.assertEqual(tar.extractfile(name + '-source/wine/COPYING.LIB').read(), b'Original Wine license\n')
            for item in ['proton', 'toolmanifest.vdf', 'version', 'LICENSE', 'LICENSE.OFL', 'PATENTS.AV1', 'COPYING.extra', 'files/share/wine/wine.inf']:
                path = redist / item
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('Keep upstream content\n')
            (redist / 'compatibilitytool.vdf').write_text('"display_name" "Proton-GameNative 12.0-1 ARM64"\n')
            # Minimal ELF fixture for file(1), not a runnable compiler output.
            elf = b'\x7fELF\x02\x01\x01' + b'\0' * 9 + struct.pack('<HHIQQQIHHHHHH', 2, 183, 1, 0, 0, 0, 0, 64, 0, 0, 0, 0, 0)
            bindir = redist / 'files/bin-arm64'
            bindir.mkdir(parents=True)
            for name_bin in ('wine', 'wineserver'):
                (bindir / name_bin).write_bytes(elf)
                (bindir / name_bin).chmod(0o755)
            for arch in ('aarch64-unix', 'aarch64-windows'):
                d = redist / 'files/lib/wine' / arch
                d.mkdir(parents=True)
                (d / 'payload').write_text('payload')
            (redist / 'license-link').symlink_to('LICENSE')
            args = ['bash', SCRIPTS / 'package-build.sh', 'binary', *common, '--tree', redist, '--sources', sources, '--output', output]
            run(*args)
            with tarfile.open(output / (name + '.tar.gz')) as tar:
                self.assertEqual({n.split('/')[0] for n in tar.getnames()}, {name})
                for item in ('LICENSE', 'LICENSE.OFL', 'PATENTS.AV1', 'COPYING.extra'):
                    self.assertEqual(tar.extractfile(name + '/' + item).read(), b'Keep upstream content\n')
                self.assertTrue(tar.getmember(name + '/license-link').issym())
                self.assertEqual(tar.getmember(name + '/files/bin-arm64/wine').mode & 0o777, 0o755)
            for archive in output.glob('*.tar.gz'):
                self.assertEqual(Path(str(archive) + '.sha256').read_text(), f'{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n')
            self.assertNotEqual(run(*args, ok=False).returncode, 0)  # No overwrites.
            (redist / 'files/bin-arm64/wine').write_text('wrong architecture')
            bad = base / 'bad'
            self.assertNotEqual(run(*args[:-1], bad, ok=False).returncode, 0)
            self.assertFalse(list(bad.glob('*.tar.gz')))


if __name__ == '__main__':
    unittest.main()
