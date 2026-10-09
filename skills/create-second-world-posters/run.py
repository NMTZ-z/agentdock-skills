#!/usr/bin/env python3
"""Portable JSON entry point. Optional poster upload; no automatic installation."""
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def execute(data):
    action = data.get('skill_action')
    if action == 'status':
        dependencies = {name: importlib.util.find_spec(name) is not None
                        for name in ('numpy', 'PIL', 'scipy')}
        dependencies.update({name: shutil.which(name) is not None for name in ('ffmpeg', 'ffprobe')})
        return {'ok': True, 'skill': 'create-second-world-posters', 'version': '1.1.1',
                'ready': all(dependencies.values()), 'dependencies': dependencies,
                'poster_ready': dependencies['PIL'] and bool(os.environ.get('SENSENOVA_API_KEY')),
                'missing_poster_configuration': [] if os.environ.get('SENSENOVA_API_KEY') else ['SENSENOVA_API_KEY'],
                'capabilities': ['design-guidance', 'sensenova-poster', 'water-mask-picker', 'masked-water-transport', 'pair-check', 'motion-audit'],
                'limits': ['Poster generation uploads the prepared photo canvas to the configured SenseNova service; visual review required',
                           '2D texture motion; no native Live Photo or video model']}
    if action in ('prepare', 'poster', 'select_motion'):
        script = 'motion_picker.py' if action == 'select_motion' else 'poster_tools.py'
        response = subprocess.run([sys.executable, '-B', str(ROOT/'scripts'/script)],
                                  input=json.dumps(data), capture_output=True, text=True)
        try:
            result = json.loads(response.stdout)
        except (ValueError, TypeError):
            return {'ok': False, 'code': 'WORKER_FAILED', 'message': 'Worker could not start or returned invalid JSON; check dependencies.'}
        result['skill_action'] = action
        return result
    commands = {
        'animate': ('animate_water_transport.py', ('image', 'video', 'config')),
        'check_pair': ('check_pair.py', ('image', 'video')),
        'audit_motion': ('audit_motion.py', ('video',)),
    }
    if action not in commands:
        raise ValueError('Unknown skill_action; use status, prepare, poster, select_motion, animate, check_pair or audit_motion')
    script, required = commands[action]
    for key in required:
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError(f'{key} must be a nonempty path string')
    args = [sys.executable, '-B', str(ROOT/'scripts'/script)]
    if action == 'animate':
        config = json.loads(Path(data['config']).read_text(encoding='utf-8'))
        if not isinstance(config, dict):
            raise ValueError('Motion config must be a JSON object')
        expected = config.get('image_sha256')
        if expected and hashlib.sha256(Path(data['image']).read_bytes()).hexdigest() != expected:
            return {'ok':False,'code':'STALE_MOTION_SELECTION','message':'Poster changed after selection; select the water mask again.'}
        args += [data['image'], data['video'], '--config', data['config']]
        if data.get('report'): args += ['--report', data['report']]
        if data.get('overwrite') is True: args += ['--overwrite']
    elif action == 'check_pair':
        args += [data['image'], data['video']]
        if data.get('before'): args += ['--before', data['before']]
        for box in data.get('unchanged_boxes', []):
            args += ['--unchanged-box', ','.join(map(str, box))]
    else:
        args += [data['video']]
        if data.get('roi'): args += ['--roi', ','.join(map(str, data['roi']))]
        if data.get('width'): args += ['--width', str(data['width'])]
        for key in ('qa', 'report'):
            if data.get(key): args += ['--'+key, data[key]]
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode:
        diagnosis = (result.stderr or result.stdout).strip().splitlines()
        return {'ok': False, 'code': 'EXECUTION_FAILED',
                'message': diagnosis[-1] if diagnosis else 'Worker failed', 'skill_action': action}
    return {'ok': True, 'skill_action': action, 'result': json.loads(result.stdout.strip().splitlines()[-1])}


def main():
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, dict): raise ValueError('stdin must contain a JSON object')
        result = execute(data)
    except (ValueError, TypeError, KeyError) as error:
        result = {'ok': False, 'code': 'INVALID_INPUT', 'message': str(error)}
    except (OSError, ImportError) as error:
        result = {'ok': False, 'code': 'DEPENDENCY_OR_IO_ERROR', 'message': str(error)}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
