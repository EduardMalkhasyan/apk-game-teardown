"""Unpack an APK/XAPK/APKS/APKM into a work folder, treating it as a hostile archive.

Writes splits/ (the bundle's own entries) and unzipped/ (every split merged) under the
output folder. The base APK goes first and its files win. A later file under assets/
whose content differs from the one already merged is kept next to it, with the split's
name in the file name: Unity split builds put a different data.unity3d in the APK and
in the OBB, and both are needed. Identical duplicates are skipped. Refuses entries that
would land outside the target, skips symlinks, caps the bytes written and stops on a
time budget. It never runs anything from the package. Standard library only.
"""
import argparse
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import time
import zipfile
import zlib

REPOSITORY = Path(__file__).resolve().parent.parent
CHUNK = 1024 * 1024


class Budget:
    def __init__(self, max_bytes, seconds):
        self.max_bytes = max_bytes
        self.deadline = time.monotonic() + seconds
        self.written = 0

    def charge(self, count):
        self.written += count
        if self.written > self.max_bytes:
            raise RuntimeError(f'Byte cap exceeded ({self.max_bytes} bytes); is this a decompression bomb?')
        if time.monotonic() > self.deadline:
            raise RuntimeError('Time budget exceeded')


def safe_target(root, name):
    """The path an entry may be written to, or None when the name is unsafe."""
    pure = PurePosixPath(name.replace('\\', '/'))
    if pure.is_absolute() or '..' in pure.parts or not pure.parts:
        return None
    target = root.joinpath(*pure.parts)
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError:
        return None
    return target


def same_content(path, entry):
    """True when the file on disk holds exactly the bytes of the archive entry."""
    if path.stat().st_size != entry.file_size:
        return False
    crc = 0
    with path.open('rb') as handle:
        while True:
            block = handle.read(CHUNK)
            if not block:
                break
            crc = zlib.crc32(block, crc)
    return crc == entry.CRC


def split_tag(member):
    """Short name of a split for tagging its copies: 'main' for main.225.com.x.obb."""
    stem = member.name[:-len(member.suffix)] if member.suffix else member.name
    if member.suffix.lower() == '.obb':
        stem = stem.split('.')[0]
    return re.sub(r'[^\w.-]', '_', stem)[:40] or 'split'


def tagged_target(target, tag, entry):
    """Free path next to target carrying the split tag, or None if an identical copy is already there."""
    for index in range(1, 100):
        candidate = target.with_name(f'{target.stem}.{tag}{"" if index == 1 else f"-{index}"}{target.suffix}')
        if not candidate.exists():
            return candidate
        if same_content(candidate, entry):
            return None
    raise RuntimeError(f'Too many differing copies of {entry.filename}')


def extract(archive, root, budget, report, overwrite=False, tag=None):
    for entry in archive.infolist():
        if entry.is_dir():
            continue
        if stat.S_ISLNK(entry.external_attr >> 16):
            report['skipped'].append({'entry': entry.filename, 'reason': 'symlink'})
            continue
        target = safe_target(root, entry.filename)
        if target is None:
            report['skipped'].append({'entry': entry.filename, 'reason': 'unsafe path'})
            continue
        if target.exists() and not overwrite:
            in_assets = PurePosixPath(entry.filename.replace('\\', '/')).parts[0] == 'assets'
            if tag is None or not in_assets or same_content(target, entry):
                report['collisions'] += 1
                continue
            target = tagged_target(target, tag, entry)
            if target is None:
                report['collisions'] += 1
                continue
            report['renamed'].append({'entry': entry.filename, 'split': tag,
                                      'kept_as': target.relative_to(root).as_posix()})
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(entry) as source, target.open('wb') as sink:
            while True:
                block = source.read(CHUNK)
                if not block:
                    break
                budget.charge(len(block))
                sink.write(block)
        report['files'] += 1


def holds_code(path):
    if not path.is_file() or not zipfile.is_zipfile(path):
        return False
    with zipfile.ZipFile(path) as archive:
        return 'classes.dex' in archive.namelist()


def unpack(package, output, max_bytes=16 * 1024**3, seconds=900):
    package = Path(package).resolve(strict=True)
    output = Path(output).resolve()
    try:
        output.relative_to(REPOSITORY)
    except ValueError:
        pass
    else:
        raise ValueError('The output folder must be outside this repository')
    splits = output / 'splits'
    merged = output / 'unzipped'
    splits.mkdir(parents=True, exist_ok=True)
    merged.mkdir(parents=True, exist_ok=True)
    budget = Budget(max_bytes, seconds)
    report = {'input': str(package), 'container': None, 'splits': [], 'files': 0,
              'collisions': 0, 'renamed': [], 'skipped': [], 'warnings': []}
    if not zipfile.is_zipfile(package):
        raise ValueError('Not a ZIP-based package')
    with zipfile.ZipFile(package) as outer:
        names = [entry.filename for entry in outer.infolist()]
        nested = [name for name in names if name.lower().endswith(('.apk', '.obb'))]
        if 'AndroidManifest.xml' in names and not nested:
            report['container'] = 'apk'
            report['splits'].append(package.name)
            extract(outer, merged, budget, report)
        else:
            report['container'] = 'bundle'
            extract(outer, splits, budget, report)
    if report['container'] == 'bundle':
        # The base holds classes.dex and goes first, so an asset pack or config split can never shadow its manifest.
        order = sorted(splits.rglob('*'), key=lambda p: (not holds_code(p), 'config.' in p.name, p.name))
        for member in order:
            if not member.is_file() or member.suffix.lower() not in {'.apk', '.obb'}:
                continue
            if not zipfile.is_zipfile(member):
                report['warnings'].append('Not a ZIP, left in splits/: ' + member.name)
                continue
            with zipfile.ZipFile(member) as inner:
                extract(inner, merged, budget, report, tag=split_tag(member))
            report['splits'].append(member.name)
    if report['renamed']:
        report['warnings'].append(
            f"{len(report['renamed'])} files under assets/ differ between splits; the later copies were kept "
            f"with the split name in the file name, e.g. {report['renamed'][0]['kept_as']}. Load them all: "
            'Unity split builds keep different content in the APK and the OBB under the same name.')
    report['bytes_written'] = budget.written
    if not (merged / 'assets').exists():
        report['warnings'].append('No assets/ folder after unpacking: the bundle may be incomplete.')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--max-bytes', type=int, default=16 * 1024**3)
    parser.add_argument('--budget', type=int, default=900, help='seconds')
    args = parser.parse_args()
    try:
        report = unpack(args.package, args.output, args.max_bytes, args.budget)
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as exc:
        shutil.rmtree(args.output / 'unzipped', ignore_errors=True)
        parser.exit(2, f'Unpack failed: {exc}\n')
    json.dump(report, sys.stdout, indent=2)
    print()


if __name__ == '__main__':
    main()
