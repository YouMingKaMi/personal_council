#!/usr/bin/env python3
"""First installation on a Linux host already using Caddy; never uploads local data."""
import argparse
import datetime
import os
import pwd
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

def run(*args):
    return subprocess.run(args,check=True,capture_output=True,text=True)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--origin',required=True);args=parser.parse_args()
    u=urlparse(args.origin)
    if u.scheme!='https' or not re.fullmatch(r'[a-z0-9.-]+:9443',u.netloc) or u.path or u.query or u.fragment:
        raise SystemExit('Use an HTTPS hostname on port 9443')
    root=Path('/opt/personal-council-capture/app')
    unit=Path('/etc/systemd/system/personal-council-capture.service')
    if unit.exists():raise SystemExit('Service already exists; review before upgrading')
    if not (root/'capture_relay.py').is_file():raise SystemExit('Application files missing')
    user='council-capture'
    try:pwd.getpwnam(user)
    except KeyError:run('useradd','--system','--no-create-home','--shell','/usr/sbin/nologin',user)
    caddy=Path('/etc/caddy/Caddyfile');original=caddy.read_text()
    if '# personal-council-capture' in original:raise SystemExit('Capture site already configured')
    # A hostname must use one certificate automation policy across ports.
    # Reuse the existing site's TLS directive verbatim, without printing secrets.
    lines=original.splitlines(); tls_lines=[]; in_site=False; depth=0; i=0
    while i<len(lines):
        line=lines[i]
        if not in_site and re.match(r'^https://'+re.escape(u.hostname)+r':\d+\s*\{\s*$',line):
            in_site=True; depth=1; i+=1; continue
        if in_site:
            if line.strip().startswith('tls '):
                tls_lines.append(line); tls_depth=line.count('{')-line.count('}')
                while tls_depth>0:
                    i+=1; line=lines[i]; tls_lines.append(line); tls_depth+=line.count('{')-line.count('}')
                break
            depth+=line.count('{')-line.count('}')
            if depth<=0:in_site=False
        i+=1
    block='\n# personal-council-capture\n'+args.origin+' {\n'+'\n'.join(tls_lines)+'\n    reverse_proxy 127.0.0.1:8890\n}\n'
    candidate=caddy.with_name('Caddyfile.capture-candidate');candidate.write_text(original+block)
    try:run('caddy','validate','--config',str(candidate),'--adapter','caddyfile')
    except Exception:
        candidate.unlink();raise
    backup=caddy.with_name('Caddyfile.before-capture-'+datetime.datetime.now().strftime('%Y%m%d%H%M%S'))
    shutil.copy2(caddy,backup)
    unit.write_text('[Unit]\nDescription=Personal Council private mobile inbox\nAfter=network-online.target\nWants=network-online.target\n\n[Service]\nType=simple\nUser='+user+'\nGroup='+user+'\nWorkingDirectory='+str(root)+'\nExecStart=/usr/bin/python3 '+str(root)+'/capture_relay.py --data /var/lib/personal-council-capture --origin '+args.origin+' --port 8890\nRestart=on-failure\nRestartSec=5\nStateDirectory=personal-council-capture\nStateDirectoryMode=0700\nUMask=0077\nNoNewPrivileges=true\nPrivateTmp=true\nProtectSystem=strict\nProtectHome=true\nRestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX\n\n[Install]\nWantedBy=multi-user.target\n')
    run('systemctl','daemon-reload');run('systemctl','enable','--now','personal-council-capture')
    try:
        caddy.write_text(original+block)
        run('systemctl','reload','caddy')
    except Exception:
        caddy.write_text(original);run('systemctl','reload','caddy');raise
    finally:candidate.unlink(missing_ok=True)
    if shutil.which('ufw'):
        result=run('ufw','status')
        if 'Status: active' in result.stdout:run('ufw','allow','9443/tcp','comment','Personal Council mobile inbox')
    print('Installed private relay; existing sites retained. Credentials are not printed.')

if __name__=='__main__':main()
