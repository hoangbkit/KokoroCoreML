#!/usr/bin/env python3
"""Fail a shipping build if synthetic Kokoro bundles or model metadata are present."""
import argparse
import json
from pathlib import Path

from coremltools.proto import Model_pb2

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('bundle', type=Path, help='Staged Kokoro runtime bundle before Xcode model compilation')
args = parser.parse_args()
root = args.bundle
if root.is_symlink():
    parser.error('Bundle root must not be a symlink')
manifest = json.loads((root / 'KokoroRuntimeManifest.json').read_text())
if ('synthetic_fixture' in manifest or str(manifest.get('bundle_profile', '')).startswith('fixture')
        or manifest.get('hf_provenance_verified') is not True):
    parser.error('Shipping assets must have verified production provenance and no fixture marker')
for package in manifest['model_packages']:
    relative = Path(package['path'])
    if relative.is_absolute() or '..' in relative.parts or '\\' in package['path']:
        parser.error('Invalid model path')
    path = root / relative / 'Data/com.apple.CoreML/model.mlmodel'
    if not path.resolve().is_relative_to(root.resolve()):
        parser.error('Model specification escapes bundle root')
    spec = Model_pb2.Model()
    spec.ParseFromString(path.read_bytes())
    if any(key.startswith('kokoro.synthetic') for key in spec.description.metadata.userDefined):
        parser.error(f'Synthetic model rejected: {relative}')
print('No synthetic Kokoro assets detected; existing production digest verification still applies.')
