#!/usr/bin/env python3
"""Construct synthetic packages without compiling, loading, or predicting them."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import coremltools as ct
from coremltools.converters.mil import Builder as mb, Function, Program
from coremltools.converters.mil.mil import types
import numpy as np

REPO = Path(__file__).resolve().parents[2]
RUNTIME = REPO / 'swift-tts/Sources/KokoroTTS/Resources/KokoroRuntime'
CONTRACT = RUNTIME / 'KokoroFixtureContract.json'
PINNED = {'coremltools': '9.0', 'numpy': '2.2.6', 'protobuf': '6.33.0'}
NUMPY_DTYPES = {'int32': np.int32, 'float32': np.float32, 'float16': np.float16}
MIL_DTYPES = {'int32': types.int32, 'float32': types.fp32, 'float16': types.fp16}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def digest(path: Path, relative: str) -> dict:
    data = path.read_bytes()
    return {'path': relative, 'bytes': len(data), 'sha256': sha256(data)}


def package_digest(package: Path) -> dict:
    files = []
    tree = hashlib.sha256()
    for file in sorted(p for p in package.rglob('*') if p.is_file()):
        relative = file.relative_to(package).as_posix()
        entry = digest(file, relative)
        files.append(entry)
        for field in (relative, str(entry['bytes']), entry['sha256']):
            tree.update(field.encode('utf-8'))
            tree.update(b'\0')
    return {'path': 'coreml/' + package.name, 'tree_sha256': tree.hexdigest(),
            'file_count': len(files), 'bytes': sum(f['bytes'] for f in files), 'files': files}


def filled(tensor: dict, value: float):
    # A scalar plus a fill op avoids storing full encoder tensors as weights.
    return mb.fill(shape=tensor['shape'], value=np.float32(value), name=tensor['name'])


def program_for(model: dict) -> Program:
    inputs = {t['name']: mb.placeholder(shape=tuple(t['shape']),
              dtype=MIL_DTYPES[t['dtype']])
              for t in model['inputs']}
    program = Program()
    with Function(inputs, opset_version=ct.target.iOS18) as function:
        outputs = []
        for tensor in model['outputs']:
            name = tensor['name']
            if name == 'pred_dur':
                # One frame per valid token; padded positions get zero frames.
                present = mb.not_equal(x=function.inputs['attention_mask'], y=np.int32(0))
                value = mb.cast(x=present, dtype='int32', name=name)
            elif name == 's' and model['stage'] == 'duration':
                value = mb.slice_by_index(x=function.inputs['ref_s'], begin=[0, 128],
                                          end=[1, 256], name=name)
            elif name == 'ref_s_out':
                value = mb.identity(x=function.inputs['ref_s'], name=name)
            elif name in ('F0_pred', 'N_pred'):
                # Exercise the required stage mask at the 2x output resolution.
                repeated = mb.upsample_nearest_neighbor(
                    x=mb.expand_dims(x=function.inputs['mask'], axes=[2]),
                    scale_factor_height=1, scale_factor_width=2)
                mask = mb.squeeze(x=repeated, axes=[1, 2])
                value = mb.mul(x=mask, y=np.float32(220 if name == 'F0_pred' else 0.01), name=name)
            elif name == 'x_pre':
                mask = mb.upsample_nearest_neighbor(
                    x=mb.expand_dims(x=function.inputs['mask'], axes=[2]),
                    scale_factor_height=1, scale_factor_width=2)
                mask = mb.squeeze(x=mask, axes=[2])
                value = mb.tile(x=mb.mul(x=mask, y=np.float32(0.01)), reps=[1, 512, 1], name=name)
            elif name == 'waveform':
                count = int(np.prod(tensor['shape']))
                time = np.arange(count, dtype=np.float64) / 24000.0
                tone = (0.02 * np.sin(2 * np.pi * 440 * time)).astype(np.float32)
                # The complete 15s output is intentional: the runtime trims it
                # to 600 samples per valid duration frame and suppresses punctuation.
                value = mb.const(val=tone.reshape(tensor['shape']),
                                 name=name if tensor['dtype'] == 'float32' else name + '_float32')
                if tensor['dtype'] == 'float16':
                    value = mb.cast(x=value, dtype='fp16', name=name)
            else:
                value = filled(tensor, 0.01)
            outputs.append(value)
        function.set_outputs(outputs)
    program.add_function('main', function)
    return program


def build(root: Path, version: str, revision: str) -> None:
    contract = json.loads(CONTRACT.read_text())
    for directory in ('coreml', 'voices', 'runtime'):
        (root / directory).mkdir(parents=True)
    packages = []
    for model in contract['models']:
        path = root / 'coreml' / model['name']
        outputs = [ct.TensorType(name=t['name'], dtype=NUMPY_DTYPES[t['dtype']])
                   for t in model['outputs']]
        converted = ct.convert(program_for(model), source='milinternal', convert_to='mlprogram',
                               minimum_deployment_target=ct.target.iOS18,
                               compute_precision=ct.precision.FLOAT32,
                               outputs=outputs, skip_model_load=True)
        converted.short_description = 'SYNTHETIC Kokoro integration fixture; not a speech model'
        converted.user_defined_metadata['kokoro.synthetic_fixture'] = 'fixture-executable-v1'
        converted.user_defined_metadata['kokoro.generator_revision'] = revision
        converted.save(str(path))
        packages.append(package_digest(path))
    voices = []
    # 128 rows allow normal length-based voice selection; values are synthetic.
    for index, name in enumerate(('af_heart', 'af_bella', 'am_michael')):
        path = root / 'voices' / (name + '.bin')
        values = np.full((128, 256), (index + 1) * 0.001, dtype='<f4')
        path.write_bytes(values.tobytes())
        voices.append(digest(path, 'voices/' + path.name))
    vocab = root / 'runtime' / 'kokoro-vocab.json'
    shutil.copyfile(RUNTIME / vocab.name, vocab)
    hnsf = root / 'runtime' / 'hnsf_weights.json'
    write_json(hnsf, {'linear_weights': [1.0] + [0.0] * 8, 'linear_bias': 0.0})
    shutil.copyfile(CONTRACT, root / 'KokoroFixtureContract.json')
    write_json(root / 'KokoroRuntimeManifest.json', {
        'schema_version': 1, 'sdk_commit': revision,
        'hf_repo_id': '', 'hf_revision': '', 'hf_provenance_verified': False,
        'hf_download_manifest_sha256': '', 'bundle_profile': contract['profile'],
        'synthetic_fixture': {'kind': 'synthetic-coreml', 'contract_version': 1,
                              'generator_revision': revision, 'artifact_version': version},
        'minimum_platforms': {'iOS': '18.0', 'macOS': '15.0'},
        'supported_languages': ['en-US'], 'buckets': [15], 'duration_token_sizes': [128],
        'model_packages': packages, 'voices': voices,
        'runtime_assets': {'vocab': digest(vocab, 'runtime/' + vocab.name),
                           'hnsf_weights': digest(hnsf, 'runtime/' + hnsf.name)},
    })
    write_json(root / 'FixtureProvenance.json', {
        'kind': 'synthetic-coreml', 'artifact_version': version, 'generator_revision': revision,
        'contract_sha256': sha256(CONTRACT.read_bytes()), 'toolchain': PINNED,
        'production_contract_source': contract['production_contract_source'],
        'runtime_validation': 'not-performed-by-generator',
        'reproducibility': 'equivalent contracts and deterministic outputs; package UUIDs may differ',
    })


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=REPO / 'testfixtures/kokoro')
    parser.add_argument('--version', required=True, help='Matching package version, e.g. 1.1.0')
    args = parser.parse_args()
    for dependency, version in PINNED.items():
        installed = importlib.metadata.version(dependency)
        if installed != version:
            parser.error(f'{dependency} {version} is required; found {installed}')
    target = args.output.absolute()
    if target.exists():
        parser.error(f'Output already exists: {target}; select an empty output location')
    if not args.version or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-' for c in args.version):
        parser.error('Version must contain only letters, numbers, dots, and hyphens')
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip()
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='kokoro-fixture-', dir=target.parent) as temporary:
        staged = Path(temporary) / 'kokoro'
        build(staged, args.version, revision)
        staged.rename(target)
    print(f'Generated {target}; Core ML compilation/prediction has not been performed.')


if __name__ == '__main__':
    main()
