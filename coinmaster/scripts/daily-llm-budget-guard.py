#!/usr/bin/env python3
import calendar
import json
import os
import subprocess
import sys
import time
from glob import glob
from pathlib import Path

JOB_ID = os.environ.get('COINMASTER_DAILY_JOB_ID', '823f5ffd-f26d-4c36-ac3f-e154149a1358')
JOB_NAME = os.environ.get('COINMASTER_DAILY_JOB_NAME', 'Coinmaster Daily LLM Insight')
THRESHOLD = int(os.environ.get('COINMASTER_DAILY_TOKEN_BUDGET', '300000'))
TELEGRAM_TARGET = os.environ.get('COINMASTER_ALERT_TARGET', '96211907')
STATE_PATH = Path(os.environ.get('COINMASTER_DAILY_GUARD_STATE', '/root/.openclaw/workspace/coinmaster/coinmaster/.ops/daily-llm-budget-guard-state.json'))
SESSIONS_GLOB = os.environ.get('OPENCLAW_SESSIONS_GLOB', '/root/.openclaw/agents/main/sessions/*.jsonl')


def utc_day_start_ts() -> float:
    now = time.time()
    g = time.gmtime(now)
    return float(calendar.timegm((g.tm_year, g.tm_mon, g.tm_mday, 0, 0, 0, 0, 0, 0)))


def run_cmd(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(args, check=check, text=True, capture_output=True)


def load_jobs() -> list[dict]:
    out = run_cmd(['openclaw', 'cron', 'list', '--json'])
    data = json.loads(out.stdout)
    return data.get('jobs', [])


def job_enabled(jobs: list[dict]) -> bool:
    for job in jobs:
        if job.get('id') == JOB_ID:
            return bool(job.get('enabled'))
    return False


def scan_tokens_since_day_start() -> tuple[int, int]:
    total_tokens = 0
    matched_sessions = 0
    day_start = utc_day_start_ts()

    for path in glob(SESSIONS_GLOB):
        try:
            st = os.stat(path)
        except FileNotFoundError:
            continue
        if st.st_mtime < day_start:
            continue

        tagged = False
        session_tokens = 0
        with open(path, 'r', encoding='utf-8') as fh:
            for idx, line in enumerate(fh):
                try:
                    obj = json.loads(line)
                except Exception:
                    continue

                if not tagged and idx < 12 and obj.get('type') == 'message':
                    msg = obj.get('message') or {}
                    if msg.get('role') == 'user':
                        parts = msg.get('content') or []
                        if isinstance(parts, list) and parts:
                            text = str((parts[0] or {}).get('text', ''))
                            if text.startswith(f'[cron:{JOB_ID}]'):
                                tagged = True

                if obj.get('type') != 'message':
                    continue
                msg = obj.get('message') or {}
                if msg.get('role') != 'assistant':
                    continue
                usage = msg.get('usage') or {}
                total = usage.get('totalTokens', usage.get('total_tokens', 0)) or 0
                try:
                    session_tokens += int(total)
                except Exception:
                    pass

        if tagged:
            matched_sessions += 1
            total_tokens += session_tokens

    return total_tokens, matched_sessions


def read_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text(encoding='utf-8'))
    except Exception:
        return {}


def write_state(data: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def send_alert(total_tokens: int, matched_sessions: int) -> None:
    message = (
        '🚨 Coinmaster daily AI budget guard triggered\n'
        f'- Job: {JOB_NAME}\n'
        f'- Job ID: {JOB_ID}\n'
        f'- UTC day usage: {total_tokens} tokens\n'
        f'- Budget: {THRESHOLD} tokens/day\n'
        f'- Sessions counted today: {matched_sessions}\n'
        '- Action: cron job auto-disabled\n'
        '- Next step: review prompt / model / artifacts before re-enabling.'
    )
    run_cmd([
        'openclaw', 'message', 'send',
        '--channel', 'telegram',
        '--target', TELEGRAM_TARGET,
        '--message', message,
    ])


def main() -> int:
    jobs = load_jobs()
    enabled = job_enabled(jobs)
    total_tokens, matched_sessions = scan_tokens_since_day_start()
    state = read_state()
    today = time.strftime('%Y-%m-%d', time.gmtime())

    state.update({
        'jobId': JOB_ID,
        'jobName': JOB_NAME,
        'threshold': THRESHOLD,
        'lastCheckUtc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'todayUtc': today,
        'todayTokens': total_tokens,
        'todaySessions': matched_sessions,
        'jobEnabledAtCheck': enabled,
    })

    already_alerted_today = state.get('lastAlertDayUtc') == today
    triggered = total_tokens > THRESHOLD and enabled

    if triggered:
        run_cmd(['openclaw', 'cron', 'disable', JOB_ID])
        if not already_alerted_today:
            send_alert(total_tokens, matched_sessions)
            state['lastAlertDayUtc'] = today
            state['lastAction'] = 'disabled_and_alerted'
        else:
            state['lastAction'] = 'disabled_already_alerted_today'
    else:
        state['lastAction'] = 'noop'

    write_state(state)
    print(json.dumps(state, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
