#!/usr/bin/env python3
"""Package a generated fixture bundle with stable archive metadata and a checksum."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--bundle', type=Path, required=True)
parser.add_argument('--output-directory', type=Path, default=Path('dist'))
args = parser.parse_args()
root = args.bundle.resolve()
manifest = json.loads((root / 'KokoroRuntimeManifest.json').read_text())
fixture = manifest.get('synthetic_fixture', {})
version = fixture.get('artifact_version', '')
if manifest.get('bundle_profile') != 'fixture-executable-v1' or fixture.get('kind') != 'synthetic-coreml' or manifest.get('hf_provenance_verified') is not False:
    parser.error('Expected a truthfully labeled executable fixture bundle')
if not re.fullmatch(r'[A-Za-z0-9.-]+', version):
    parser.error('Invalid artifact version')
args.output_directory.mkdir(parents=True, exist_ok=True)
archive = args.output_directory / f'kokoro-fixture-{version}.tar.gz'
if archive.exists():
    parser.error(f'Archive already exists: {archive}')
with archive.open('xb') as output, gzip.GzipFile(filename='', fileobj=output, mode='wb', mtime=0) as compressed:
    with tarfile.open(fileobj=compressed, mode='w|') as tar:
        for file in sorted(root.rglob('*')):
            if file.is_symlink():
                raise ValueError(f'Symlinks are forbidden in fixture artifacts: {file}')
            if not file.is_file():
                continue
            payload = file.read_bytes()
            info = tarfile.TarInfo('kokoro/' + file.relative_to(root).as_posix())
            info.size = len(payload)
            info.mode = 0o644
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = ''
            tar.addfile(info, io.BytesIO(payload))
checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
archive.with_name(archive.name + '.sha256').write_text(f'{checksum}  {archive.name}\n')
print(archive)
