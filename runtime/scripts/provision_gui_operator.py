#!/usr/bin/env python3
"""Keep the GUI's one password in macOS Keychain; send only its hash to the VPS.

Run with PYTHONPATH=runtime runtime/.venv/bin/python. Neither the password nor
the runtime automation token is printed, placed in command arguments, or saved
in the repository.
"""
from __future__ import annotations

import argparse
import ctypes
import re
import secrets
import shlex
import subprocess
import sys

from coinmaster.api.gui_auth import password_hash


SERVICE = "coinmaster24.com CoinMaster operator"
LEGACY_SERVICE = "cm.f-ai.studio CoinMaster operator"
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


def store_keychain_password(password: str) -> None:
    """Store a new secret without exposing it in process arguments or output."""
    security = ctypes.CDLL("/System/Library/Frameworks/Security.framework/Security")
    security.SecKeychainAddGenericPassword.argtypes = [
        ctypes.c_void_p, ctypes.c_uint32, ctypes.c_char_p,
        ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32,
        ctypes.c_char_p, ctypes.c_void_p,
    ]
    security.SecKeychainAddGenericPassword.restype = ctypes.c_int32
    service, account, secret = SERVICE.encode(), b"operator", password.encode()
    status = security.SecKeychainAddGenericPassword(
        None, len(service), service, len(account), account,
        len(secret), secret, None,
    )
    if status != 0:
        raise SystemExit(f"Keychain rejected operator credential creation ({status}); VPS unchanged")


def keychain_password(service: str = SERVICE) -> str:
    found = subprocess.run(
        ["security", "find-generic-password", "-a", "operator", "-s", service, "-w"],
        capture_output=True, text=True, check=False,
    )
    return found.stdout.rstrip("\n") if found.returncode == 0 else ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="verified root@host SSH target")
    args = parser.parse_args()
    if not re.fullmatch(r"root@[A-Za-z0-9.:-]+", args.host):
        parser.error("host must be a verified root@host target")
    password = keychain_password()
    if not password:
        # The public host changed, not the operator. Reuse the existing secret.
        password = keychain_password(LEGACY_SERVICE) or secrets.token_urlsafe(36)
        if len(password) < 32:
            raise SystemExit("Existing Keychain operator credential is unexpectedly short; VPS unchanged")
        store_keychain_password(password)
        if keychain_password() != password:
            raise SystemExit("Keychain credential verification failed; VPS unchanged")
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
