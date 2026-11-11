"""Synthetic archives only: no game files."""
import io
from pathlib import Path
import stat
import tempfile
import unittest
import zipfile

from toolkit.unpack_package import unpack


def archive_bytes(entries):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        for name, value in entries.items():
            archive.writestr(name, value)
    return stream.getvalue()


class UnpackTests(unittest.TestCase):
    def run_unpack(self, payload, name='fixture.xapk', **options):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        package = Path(folder.name) / name
        package.write_bytes(payload)
        output = Path(folder.name) / 'work'
        return unpack(package, output, **options), output

    def test_single_apk(self):
        report, output = self.run_unpack(archive_bytes({'AndroidManifest.xml': b'm', 'assets/a.json': b'{}'}), 'a.apk')
        self.assertEqual(report['container'], 'apk')
        self.assertEqual((output / 'unzipped/assets/a.json').read_bytes(), b'{}')

    def test_bundle_merges_splits_and_base_wins(self):
        base = archive_bytes({'AndroidManifest.xml': b'base', 'assets/a.json': b'{}'})
        split = archive_bytes({'AndroidManifest.xml': b'split', 'lib/arm64-v8a/libil2cpp.so': b'x'})
        report, output = self.run_unpack(archive_bytes({'com.game.apk': base, 'config.arm64_v8a.apk': split}))
        self.assertEqual(report['container'], 'bundle')
        self.assertEqual((output / 'unzipped/AndroidManifest.xml').read_bytes(), b'base')
        self.assertTrue((output / 'unzipped/lib/arm64-v8a/libil2cpp.so').exists())
        self.assertEqual(report['collisions'], 1)

    def test_asset_pack_cannot_shadow_the_base_manifest(self):
        base = archive_bytes({'AndroidManifest.xml': b'base', 'classes.dex': b'd', 'assets/a.json': b'{}'})
        pack = archive_bytes({'AndroidManifest.xml': b'pack', 'assets/bin/Data/data.unity3d': b'x'})
        _, output = self.run_unpack(archive_bytes({'com.game.apk': base, 'UnityDataAssetPack.apk': pack}))
        self.assertEqual((output / 'unzipped/AndroidManifest.xml').read_bytes(), b'base')

    def test_obb_copy_that_differs_is_kept_next_to_the_apk_copy(self):
        # Unity split builds: the APK and the OBB both hold assets/bin/Data/data.unity3d, with different scenes.
        base = archive_bytes({'AndroidManifest.xml': b'm', 'classes.dex': b'd',
                              'assets/bin/Data/data.unity3d': b'apk scenes', 'assets/same.json': b'{}'})
        obb = archive_bytes({'assets/bin/Data/data.unity3d': b'obb scenes, much bigger',
                             'assets/same.json': b'{}', 'assets/bin/Data/resources.resource': b'r'})
        report, output = self.run_unpack(archive_bytes({
            'com.game.apk': base, 'Android/obb/com.game/main.225.com.game.obb': obb}))
        data = output / 'unzipped/assets/bin/Data'
        self.assertEqual((data / 'data.unity3d').read_bytes(), b'apk scenes')
        self.assertEqual((data / 'data.main.unity3d').read_bytes(), b'obb scenes, much bigger')
        self.assertTrue((data / 'resources.resource').exists())
        self.assertEqual(report['renamed'], [{'entry': 'assets/bin/Data/data.unity3d', 'split': 'main',
                                              'kept_as': 'assets/bin/Data/data.main.unity3d'}])
        self.assertEqual(report['collisions'], 1)  # the identical same.json
        self.assertIn('data.main.unity3d', report['warnings'][0])

    def test_differing_files_outside_assets_still_keep_the_first_copy(self):
        base = archive_bytes({'AndroidManifest.xml': b'base', 'classes.dex': b'd', 'assets/a.json': b'{}'})
        split = archive_bytes({'AndroidManifest.xml': b'split', 'resources.arsc': b'r'})
        report, output = self.run_unpack(archive_bytes({'com.game.apk': base, 'config.xxhdpi.apk': split}))
        self.assertEqual(report['renamed'], [])
        self.assertFalse(list((output / 'unzipped').glob('AndroidManifest.*.xml')))

    def test_entry_cannot_escape_target(self):
        report, output = self.run_unpack(archive_bytes({'../../evil.txt': b'x', 'AndroidManifest.xml': b'm', 'assets/a': b'y'}), 'a.apk')
        self.assertFalse((output.parent / 'evil.txt').exists())
        self.assertFalse((output.parent.parent / 'evil.txt').exists())
        self.assertEqual(report['skipped'][0]['reason'], 'unsafe path')

    def test_symlink_is_skipped(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            archive.writestr('AndroidManifest.xml', b'm')
            archive.writestr('assets/a', b'y')
            link = zipfile.ZipInfo('assets/link')
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(link, '/etc/passwd')
        report, output = self.run_unpack(stream.getvalue(), 'a.apk')
        self.assertFalse((output / 'unzipped/assets/link').exists())
        self.assertEqual(report['skipped'][0]['reason'], 'symlink')

    def test_byte_cap_stops_a_bomb(self):
        with self.assertRaises(RuntimeError):
            self.run_unpack(archive_bytes({'AndroidManifest.xml': b'm', 'assets/big': b'x' * 4096}), 'a.apk', max_bytes=1024)

    def test_refuses_output_inside_repository(self):
        repository = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as folder:
            package = Path(folder) / 'a.apk'
            package.write_bytes(archive_bytes({'AndroidManifest.xml': b'm'}))
            with self.assertRaises(ValueError):
                unpack(package, repository / 'runs' / 'x')


if __name__ == '__main__':
    unittest.main()
