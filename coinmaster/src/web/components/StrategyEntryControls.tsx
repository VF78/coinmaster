import { useEffect, useState } from 'react';
import { Card } from './Card';
import { Badge } from './Badge';
import { Button } from './Button';
import { commandHlStagegEntries, getHlStagegControls, getHlStagegProjection, type HlStagegControls, type HlStagegProjection } from '../lib/nautilusApi';
import { protectionIsFresh } from '../lib/accountPresentation';
import { verifiedControlReadback } from '../lib/controlReadback';
import { humanizeBlocker } from '../lib/traderLabels';

export function StrategyEntryControls() {
  const [state, setState] = useState<HlStagegProjection | null>(null);
  const [controls, setControls] = useState<HlStagegControls | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  async function refresh() {
    const [projection, capabilities] = await Promise.all([getHlStagegProjection(), getHlStagegControls()]);
    setState(projection); setControls(capabilities);
    return projection;
  }
  useEffect(() => {
    let active = true;
    const poll = () => { if (active) void refresh().catch(() => { if (active) { setState(null); setControls(null); } }); };
    poll(); const timer = window.setInterval(poll, 5000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);
  const ready = state?.projection_state === 'READY' && !state.recovery_required;
  const paused = state?.entry_control.state === 'PAUSED';
  const protectedNow = protectionIsFresh(state);
  async function apply(command: 'pause-new-entries' | 'resume-new-entries') {
    if (busy || !ready) return;
    setBusy(true); setNotice('');
    try {
      const result = await commandHlStagegEntries(command, crypto.randomUUID());
      const fresh = await refresh();
      if (!verifiedControlReadback(state, fresh, result.entry_control)) throw new Error('Fresh worker confirmation is unavailable. Refresh before retrying.');
      setNotice(result.entry_control === 'PAUSED' ? 'New entries paused. Existing positions remain managed.' : 'New entries resumed. Strategy eligibility still applies.');
    } catch (error) { setNotice(error instanceof Error ? error.message : 'Control update unavailable.'); }
    finally { setBusy(false); }
  }
  return <Card title="Strategy controls" actions={<Badge tone={!ready ? 'danger' : paused ? 'neutral' : 'success'}>{!ready ? 'Status unavailable' : paused ? 'Entries paused' : 'Entries running'}</Badge>}>
    <div className="strategy-controls-row"><p className="trader-note">{protectedNow ? 'Drawdown protection: ' + state?.deposit_protection?.drawdown_limit_percent + '% limit.' : 'Drawdown protection confirmation unavailable.'} Pause stops new entries while existing exposure remains managed.</p>
      <Button variant="secondary" disabled={!ready || busy || !(paused ? controls?.resume.enabled : controls?.pause.enabled)} onClick={() => void apply(paused ? 'resume-new-entries' : 'pause-new-entries')} title={humanizeBlocker((paused ? controls?.resume.blocker : controls?.pause.blocker) ?? '')}>{busy ? 'Updating…' : paused ? 'Resume new entries' : 'Pause new entries'}</Button>
    </div>{notice ? <p role="status">{notice}</p> : null}
  </Card>;
}
