#!/usr/bin/env python3
"""Explicitly requested static contract inspection; does not execute Core ML."""
import argparse
import hashlib
import json
from pathlib import Path

from coremltools.proto import Model_pb2, FeatureTypes_pb2

REPO = Path(__file__).resolve().parents[2]
CONTRACT = REPO / 'swift-tts/Sources/KokoroTTS/Resources/KokoroRuntime/KokoroFixtureContract.json'
DTYPES = {FeatureTypes_pb2.ArrayFeatureType.FLOAT32: 'float32',
          FeatureTypes_pb2.ArrayFeatureType.FLOAT16: 'float16',
          FeatureTypes_pb2.ArrayFeatureType.INT32: 'int32',
          FeatureTypes_pb2.ArrayFeatureType.DOUBLE: 'float64'}


def description(features):
    tensors = []
    for feature in features:
        if feature.type.WhichOneof('Type') != 'multiArrayType':
            raise ValueError(f'{feature.name} is not a multi-array')
        array = feature.type.multiArrayType
        if array.WhichOneof('ShapeFlexibility') is not None:
            raise ValueError(f'{feature.name} has flexible shapes; static fixture parity changed')
        tensors.append({'name': feature.name, 'dtype': DTYPES[array.dataType], 'shape': list(array.shape)})
    return sorted(tensors, key=lambda t: t['name'])


def inspect(root, expected, production):
    records = []
    for model in expected['models']:
        # Accept a runtime bundle's coreml/ directory or a bare models directory.
        base = root / 'coreml' if (root / 'coreml').is_dir() else root
        path = base / model['name'] / 'Data/com.apple.CoreML/model.mlmodel'
        payload = path.read_bytes()
        spec = Model_pb2.Model()
        spec.ParseFromString(payload)
        for field in ('inputs', 'outputs'):
            actual = description(getattr(spec.description, 'input' if field == 'inputs' else 'output'))
            target = sorted(model[field], key=lambda t: t['name'])
            if actual != target:
                raise ValueError(f'{model["name"]} {field} drift:\nexpected {target}\nactual {actual}')
        synthetic = spec.description.metadata.userDefined.get('kokoro.synthetic_fixture', '')
        if production and synthetic:
            raise ValueError(f'{model["name"]} is synthetic, not production evidence')
        if not production and synthetic != expected['profile']:
            raise ValueError(f'{model["name"]} lacks fixture metadata')
        records.append({'name': model['name'], 'spec_sha256': hashlib.sha256(payload).hexdigest()})
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--production-specs', type=Path,
                        help='Actual pinned production model specifications; weights not required')
    parser.add_argument('--production-revision', help='Exact upstream artifact revision, required with production-specs')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    if bool(args.production_specs) != bool(args.production_revision):
        parser.error('Supply both production-specs and production-revision')
    contract = json.loads(CONTRACT.read_text())
    report = {'contract_sha256': hashlib.sha256(CONTRACT.read_bytes()).hexdigest(),
              'fixture_models': inspect(args.bundle, contract, False)}
    if args.production_specs:
        report['production_models'] = inspect(args.production_specs, contract, True)
        report['production_revision'] = args.production_revision
    if args.report:
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
