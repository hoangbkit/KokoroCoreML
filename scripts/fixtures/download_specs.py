#!/usr/bin/env python3
"""Fetch only pinned production protobuf specifications for requested inspection."""
import argparse
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request

REPO = Path(__file__).resolve().parents[2]
CONTRACT = REPO / 'swift-tts/Sources/KokoroTTS/Resources/KokoroRuntime/KokoroFixtureContract.json'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--revision', required=True, help='Exact 40-character Hugging Face commit revision')
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
if not re.fullmatch(r'[0-9a-f]{40}', args.revision):
    parser.error('Use an exact lowercase 40-character artifact revision, not a moving branch')
if args.output.exists():
    parser.error('Select an empty output location')
contract = json.loads(CONTRACT.read_text())
for model in contract['models']:
    relative = Path(model['name']) / 'Data/com.apple.CoreML/model.mlmodel'
    url = ('https://huggingface.co/mattmireles/kokoro-coreml/resolve/'
           + args.revision + '/coreml/' + urllib.parse.quote(relative.as_posix(), safe='/'))
    with urllib.request.urlopen(url, timeout=60) as response:
        # Model protobufs are small; never fetch multi-megabyte weight archives.
        payload = response.read(4 * 1024 * 1024 + 1)
        if len(payload) > 4 * 1024 * 1024:
            raise ValueError(f'Specification exceeded 4 MiB: {model["name"]}')
    path = args.output / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
print(f'Fetched specifications only from {args.revision}; no production weights downloaded.')
