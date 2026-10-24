#!/usr/bin/env python3
"""Build/check pinned DG role projections. No network or lifecycle authority."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / '.codex/dg-routing-source.json'
SCHEMAS = ('work-record.schema.json', 'work-result.schema.json')
MARKER = '\nACA project constraints (additional, never authority to widen scope):\n'


def git_blob(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def project(source, overlay):
    text = source.decode('utf-8')
    if text.count('"""') != 2 or not text.endswith('"""\n'):
        raise ValueError('Unsupported canonical instruction encoding')
    return (text[:-4] + MARKER + overlay.decode('utf-8') + '"""\n').encode('utf-8')


def routing_schema(roles):
    return {
        'type': 'object', 'additionalProperties': False,
        'required': ['profile', 'model', 'reasoning_effort', 'sandbox_mode',
                     'selection_reason', 'escalation_criteria'],
        'properties': {
            'profile': {'enum': sorted(roles)},
            'model': {'enum': sorted({r['model'] for r in roles.values()})},
            'reasoning_effort': {'enum': sorted({r['model_reasoning_effort'] for r in roles.values()})},
            'sandbox_mode': {'enum': sorted({r['sandbox_mode'] for r in roles.values()})},
            'selection_reason': {'type': 'string', 'minLength': 1},
            'escalation_criteria': {'type': 'array', 'minItems': 1,
                                    'items': {'type': 'string', 'minLength': 1}},
        },
        'oneOf': [{'properties': {
            'profile': {'const': name}, 'model': {'const': role['model']},
            'reasoning_effort': {'const': role['model_reasoning_effort']},
            'sandbox_mode': {'const': role['sandbox_mode']},
        }} for name, role in sorted(roles.items())],
    }


def run(source_dir=None, root=ROOT):
    manifest = json.loads((root / '.codex/dg-routing-source.json').read_text())
    roles = {}
    for name, entry in sorted(manifest['roles'].items()):
        overlay = (root / entry['local_instructions']).read_bytes()
        if hashlib.sha256(overlay).hexdigest() != entry['local_instructions_sha256']:
            raise ValueError(f'{name}: ACA instruction drift')
        target = root / entry['source_path']
        if source_dir is not None:
            source = (source_dir / entry['source_path']).read_bytes()
        else:
            projected = target.read_bytes()
            suffix = (MARKER + overlay.decode() + '"""\n').encode()
            if not projected.endswith(suffix):
                raise ValueError(f'{name}: projection/instruction drift')
            source = projected[:-len(suffix)] + b'"""\n'
        if git_blob(source) != entry['source_blob']:
            raise ValueError(f'{name}: canonical blob mismatch')
        roles[name] = tomllib.loads(source.decode())
        expected = project(source, overlay)
        if source_dir is not None:
            target.write_bytes(expected)
        elif target.read_bytes() != expected:
            raise ValueError(f'{name}: projection mismatch')
    config_path = root / '.codex/config.toml'
    if source_dir is not None:
        lines = ['# Generated role references; model selection comes from pinned DG source.',
                 '[agents]', 'enabled = true', 'max_concurrent_threads_per_session = 4', '']
        for name, role in sorted(roles.items()):
            lines += [f'[agents.{name}]', f'description = {json.dumps(role["description"])}',
                      f'config_file = "agents/{name}.toml"', '']
        config_path.write_text('\n'.join(lines))
    config = tomllib.loads(config_path.read_text())['agents']
    if set(config) != set(roles) | {'enabled', 'max_concurrent_threads_per_session'}:
        raise ValueError('Unexpected agent selector/default')
    if config['enabled'] is not True or config['max_concurrent_threads_per_session'] != 4:
        raise ValueError('Agent enablement/concurrency drift')
    for name, role in roles.items():
        entry = config[name]
        if entry != {'description': role['description'], 'config_file': f'agents/{name}.toml'}:
            raise ValueError(f'{name}: config reference drift')
        if (config_path.parent / entry['config_file']).resolve() != (root / '.codex/agents' / (name + '.toml')).resolve():
            raise ValueError(f'{name}: config path mismatch')
    expected_routing = routing_schema(roles)
    for filename in SCHEMAS:
        path = root / 'docs/ai-dev-ops/orchestration' / filename
        schema = json.loads(path.read_text())
        if source_dir is not None:
            schema['$defs']['routing'] = expected_routing
            lines = path.read_text().splitlines()
            positions = [i for i, line in enumerate(lines) if line.startswith('    "routing": ') and '"$ref"' not in line]
            if len(positions) != 1:
                raise ValueError(f'{filename}: unsupported schema layout')
            lines[positions[0]] = '    "routing": ' + json.dumps(expected_routing) + ','
            path.write_text('\n'.join(lines) + '\n')
        elif schema['$defs']['routing'] != expected_routing:
            raise ValueError(f'{filename}: canonical route schema drift')
    print(f'PASS: {len(roles)} pinned DG roles, ACA constraints, config paths and route schemas')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, help='Regenerate only from verified pinned canonical bytes')
    args = parser.parse_args()
    try:
        run(args.source_dir)
    except (OSError, ValueError, KeyError, tomllib.TOMLDecodeError) as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        raise SystemExit(1)
