"""Portable conversion of resource.ru_maxrss; no monitoring service."""
import sys

def peak_rss_bytes(value, platform=None):
    return int(value) * (1 if (platform or sys.platform) == 'darwin' else 1024)
