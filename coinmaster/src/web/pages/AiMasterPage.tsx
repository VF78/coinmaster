import { useEffect, useMemo, useState } from 'react';
import type { AiMasterInsight, AiMasterQaItem } from '../../shared/dto.js';
import { getAiMasterSnapshot, submitAiMasterQuestion, friendlyErrorMessage } from '../lib/api';
import { formatDate } from '../lib/format';
import { Badge } from '../components/Badge';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { DataTable } from '../components/DataTable';

export function AiMasterPage() {
  const [insights, setInsights] = useState<AiMasterInsight[]>([]);
  const [qa, setQa] = useState<AiMasterQaItem[]>([]);
  const [question, setQuestion] = useState('');
  const [busy, setBusy] = useState(false);
  const [info, setInfo] = useState('');

  async function refresh() {
    const next = await getAiMasterSnapshot(100);
    setInsights(next.insights ?? []);
    setQa(next.qa ?? []);
  }

  useEffect(() => {
    refresh().catch(() => {
      setInfo('Could not load AI Master data.');
    });
  }, []);

  async function handleAsk() {
    const text = question.trim();
    if (!text) return;
    setBusy(true);
    setInfo('Submitting question...');
    try {
      await submitAiMasterQuestion(text);
      setQuestion('');
      setInfo('Question queued. Answer will appear in history and Telegram.');
      await refresh();
    } catch (error) {
      setInfo(friendlyErrorMessage(error, 'Could not submit question.'));
    } finally {
      setBusy(false);
    }
  }

  const latestInsight = insights[0] ?? null;

  const answeredCount = useMemo(() => qa.filter((x) => x.status === 'answered').length, [qa]);
  const pendingCount = useMemo(() => qa.filter((x) => x.status === 'pending').length, [qa]);

  return (
    <main className="terminal-layout">
      <Card
        title="AI Master"
        className="full-width terminal-card"
        actions={(
          <div className="actions-row">
            <Button variant="secondary" onClick={() => refresh()} disabled={busy}>Refresh</Button>
          </div>
        )}
      >
        <div className="muted" style={{ marginBottom: '0.6rem' }}>
          Daily AI analytics mirror + web Q&A history (signals are NOT sent from web).
        </div>

        <div className="stats-grid" style={{ marginBottom: '0.75rem' }}>
          <div className="stat">
            <span className="stat-label">Insights</span>
            <strong className="stat-value">{insights.length}</strong>
          </div>
          <div className="stat">
            <span className="stat-label">Answered Q&A</span>
            <strong className="stat-value">{answeredCount}</strong>
          </div>
          <div className="stat">
            <span className="stat-label">Pending Q&A</span>
            <strong className="stat-value">{pendingCount}</strong>
          </div>
        </div>

        <div style={{ display: 'grid', gap: '0.5rem', marginBottom: '0.9rem' }}>
          <label className="rules-label" htmlFor="ai-master-question">Ask AI Master</label>
          <textarea
            id="ai-master-question"
            className="rules-input"
            value={question}
            rows={3}
            placeholder="Например: Как оптимизировать текущие открытые позиции и снизить fee burn?"
            onChange={(e) => setQuestion(e.target.value)}
          />
          <div className="actions-row" style={{ justifyContent: 'space-between' }}>
            <span className="muted">{info}</span>
            <Button onClick={() => { void handleAsk(); }} disabled={busy || question.trim().length === 0}>Send question</Button>
          </div>
        </div>

        {latestInsight ? (
          <div style={{ marginBottom: '1rem', border: '1px solid var(--line)', borderRadius: '0.6rem', padding: '0.75rem' }}>
            <div className="actions-row" style={{ justifyContent: 'space-between', marginBottom: '0.35rem' }}>
              <strong>Latest daily insight</strong>
              <span className="muted">{formatDate(latestInsight.createdAt)}{latestInsight.model ? ` • ${latestInsight.model}` : ''}</span>
            </div>
            <div style={{ whiteSpace: 'pre-wrap' }}>{latestInsight.text}</div>
          </div>
        ) : (
          <p className="muted" style={{ marginBottom: '1rem' }}>No daily insights yet.</p>
        )}

        <DataTable<AiMasterQaItem>
          rows={qa}
          mobileTitle={(row) => row.question}
          mobileSubtitle={(row) => `${formatDate(row.askedAt)} • ${row.status}`}
          emptyText="No Q&A yet."
          columns={[
            { key: 'askedAt', header: 'Asked', render: (row) => formatDate(row.askedAt) },
            {
              key: 'status',
              header: 'Status',
              render: (row) => (
                <Badge tone={row.status === 'answered' ? 'success' : row.status === 'failed' ? 'danger' : 'neutral'}>
                  {row.status}
                </Badge>
              )
            },
            { key: 'question', header: 'Question', render: (row) => row.question },
            {
              key: 'answer',
              header: 'Answer',
              render: (row) => row.answer ? row.answer : row.error ? `Error: ${row.error}` : '—'
            },
          ]}
        />
      </Card>
    </main>
  );
}
