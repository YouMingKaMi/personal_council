#!/usr/bin/env python3
"""Keep the official, read-only query runtime available after login or process exit."""
import argparse
import fcntl
import json
import os
import plistlib
import re
import shlex
import subprocess
import sys
from pathlib import Path

LABEL = 'com.youmingkami.personal-council-query'


def python_command():
    stable = Path('/opt/homebrew/bin/python3')
    return str(stable) if stable.is_file() else sys.executable


def agent_config(root):
    root = Path(root).resolve()
    return {'Label': LABEL,
            'ProgramArguments': [python_command(), str(root / 'personal_query_service.py'), '--root', str(root)],
            'RunAtLoad': True, 'StartInterval': 60, 'ProcessType': 'Background',
            'WorkingDirectory': str(root),
            'StandardOutPath': str(root / 'runtime/supervisor.log'),
            'StandardErrorPath': str(root / 'runtime/supervisor-error.log')}


def ensure_runtime(root):
    root = Path(root).resolve()
    runtime = root / 'runtime'
    credential = runtime / 'control-plane.key'
    if not credential.is_file() or credential.is_symlink() or credential.stat().st_mode & 0o077:
        raise ValueError('缺少专用凭证，或凭证不是仅本人可读的普通文件')
    metadata = json.loads((runtime / 'connection.json').read_text())
    tunnel_id = metadata['tunnelId']
    if not re.fullmatch(r'tunnel_[0-9a-f]{32}', tunnel_id):
        raise ValueError('通道编号格式无效')
    client = str(root / 'tunnel-client')
    result = subprocess.run([client, 'runtimes', 'status', 'personal-council', '--json'],
                            capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise ValueError('无法核实运行状态；保留当前运行程序，稍后重试')
    state = json.loads(result.stdout)
    if not isinstance(state, dict) or type(state.get('process_running')) is not bool:
        raise ValueError('运行状态不明确；保留当前运行程序，稍后重试')
    if state['process_running']:
        return {'running': True, 'healthy': state.get('healthy'), 'ready': state.get('ready'), 'started': False}
    command = shlex.join([python_command(), str(root / 'personal_query.py')])
    result = subprocess.run([client, 'runtimes', 'connect', '--alias', 'personal-council',
        '--tunnel-id', tunnel_id, '--profile', 'personal-council', '--profile-dir', str(runtime / 'profiles'),
        '--mcp-command', command, '--runtime-api-key', 'file:' + str(credential), '--json'],
        capture_output=True, text=True, timeout=45)
    if result.returncode:
        raise ValueError('通道暂时不能恢复，稍后重试；没有修改网站记录')
    state = json.loads(result.stdout)
    return {'running': state.get('process_running'), 'healthy': state.get('healthy'),
            'ready': state.get('ready'), 'started': True}


def install(root):
    root = Path(root).resolve()
    config = agent_config(root)
    path = Path.home() / 'Library/LaunchAgents' / (LABEL + '.plist')
    if path.exists():
        previous = plistlib.loads(path.read_bytes())
        if previous.get('ProgramArguments') != config['ProgramArguments']:
            raise ValueError('已有同名服务属于其它位置，没有覆盖')
    path.parent.mkdir(parents=True, exist_ok=True)
    for key in ('StandardOutPath', 'StandardErrorPath'):
        log = Path(config[key])
        if log.is_symlink():
            raise ValueError('日志位置不能是符号链接')
        fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        os.close(fd)
        log.chmod(0o600)
    path.write_bytes(plistlib.dumps(config))
    path.chmod(0o600)
    domain = 'gui/' + str(os.getuid())
    loaded = subprocess.run(['launchctl', 'print', domain + '/' + LABEL], capture_output=True)
    if loaded.returncode:
        result = subprocess.run(['launchctl', 'bootstrap', domain, str(path)], capture_output=True)
        if result.returncode:
            raise ValueError('后台服务注册失败，现有连接保持不变')
    return {'service': LABEL, 'loginStart': True, 'recoveryCheckSeconds': 60}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--install', action='store_true')
    args = parser.parse_args()
    try:
        if args.install:
            result = install(args.root)
        else:
            lock_path = args.root / 'runtime/supervisor.lock'
            fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT, 0o600)
            with os.fdopen(fd, 'w') as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    return
                result = ensure_runtime(args.root)
        print(json.dumps(result, ensure_ascii=False))
    except (ValueError, KeyError, OSError, subprocess.TimeoutExpired):
        # Never put command output, credentials, queries or records in supervisor logs.
        print('个人查询连接暂不可用，将在下次检查时重试。', file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
