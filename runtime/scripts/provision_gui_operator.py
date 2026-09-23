#!/usr/bin/env python3
"""Keep the GUI's one password in macOS Keychain; send only its hash to the VPS.

Run with PYTHONPATH=runtime runtime/.venv/bin/python. Neither the password nor
the runtime automation token is printed, placed in command arguments, or saved
in the repository.
"""
from __future__ import annotations

import argparse
import re
import secrets
import shlex
import subprocess
import sys

from coinmaster.api.gui_auth import password_hash


SERVICE = "cm.f-ai.studio CoinMaster operator"
REMOTE = r'''
import os, re, sys, tempfile
from pathlib import Path
verifier = sys.stdin.read().strip()
if not re.fullmatch(r'scrypt\$15\$8\$1\$[0-9a-f]{64}\$[0-9a-f]{128}', verifier):
    raise SystemExit('invalid verifier')
path = Path('/etc/coinmaster-native-gui.env')
tokens = [line.split('=', 1)[1].strip().strip('"\'') for line in Path('/etc/coinmaster-paper.env').read_text().splitlines() if line.startswith('COINMASTER_RUNTIME_API_TOKEN=')]
if len(tokens) != 1 or not re.fullmatch(r'[A-Za-z0-9._~+\-]{16,256}', tokens[0]):
    raise SystemExit('existing operator token is unavailable')
fd, name = tempfile.mkstemp(prefix='.coinmaster-native-gui.', dir='/etc')
try:
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, 'w') as out:
        out.write('COINMASTER_RUNTIME_API_TOKEN=' + tokens[0] + '\n')
        out.write('COINMASTER_GUI_USERNAME=operator\n')
        out.write('COINMASTER_GUI_PASSWORD_HASH=' + verifier + '\n')
        out.flush(); os.fsync(out.fileno())
    os.replace(name, path)
except BaseException:
    try: os.unlink(name)
    except OSError: pass
    raise
print('GUI_OPERATOR_ENV_READY')
'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="verified root@host SSH target")
    args = parser.parse_args()
    if not re.fullmatch(r"root@[A-Za-z0-9.:-]+", args.host):
        parser.error("host must be a verified root@host target")
    find = subprocess.run(["security", "find-generic-password", "-a", "operator", "-s", SERVICE, "-w"], capture_output=True, text=True, check=False)
    if find.returncode == 0:
        password = find.stdout.rstrip("\n")
    else:
        password = secrets.token_urlsafe(36)
        # With -w as the final option, security reads the value from stdin.
        stored = subprocess.run(["security", "add-generic-password", "-a", "operator", "-s", SERVICE, "-w"], input=password + "\n", capture_output=True, text=True, check=False)
        if stored.returncode != 0:
            raise SystemExit("Keychain rejected operator credential creation; VPS unchanged")
    if len(password) < 32:
        raise SystemExit("Keychain operator credential is unexpectedly short")
    verifier = password_hash(password)
    remote = "python3 -c " + shlex.quote(REMOTE)
    result = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=8", args.host, remote], input=verifier, capture_output=True, text=True, check=False)
    if result.returncode != 0 or result.stdout.strip() != "GUI_OPERATOR_ENV_READY":
        raise SystemExit("VPS root-only credential provisioning failed; Keychain item retained for retry")
    print("GUI_OPERATOR_READY: password in macOS Keychain, verifier in root-only VPS environment")
    return 0


if __name__ == "__main__":
    sys.exit(main())
