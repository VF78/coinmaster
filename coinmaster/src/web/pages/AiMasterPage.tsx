import { useEffect, useMemo, useRef, useState } from 'react';
import type { AiMasterInsight, AiMasterQaItem } from '../../shared/dto.js';
import { getAiMasterSnapshot, submitAiMasterQuestion, friendlyErrorMessage } from '../lib/api';
import { formatDate } from '../lib/format';
import { Badge } from '../components/Badge';
import { Button } from '../components/Button';
import { Card } from '../components/Card';

type ChatRole = 'assistant' | 'user' | 'system';

interface ChatMessage {
  id: string;
  ts: string;
  role: ChatRole;
  text: string;
  meta?: string;
}

function toChatMessages(insights: AiMasterInsight[], qa: AiMasterQaItem[]): ChatMessage[] {
  const rows: ChatMessage[] = [];

  for (const insight of insights) {
    rows.push({
      id: `insight:${insight.id}`,
      ts: insight.createdAt,
      role: 'assistant',
      text: insight.text,
      meta: `Daily report${insight.model ? ` • ${insight.model}` : ''}`,
    });
  }

  for (const item of qa) {
    rows.push({
      id: `q:${item.id}`,
      ts: item.askedAt,
      role: 'user',
      text: item.question,
      meta: 'You',
    });

    if (item.status === 'answered' && item.answer) {
      rows.push({
        id: `a:${item.id}`,
        ts: item.answeredAt ?? item.askedAt,
        role: 'assistant',
        text: item.answer,
        meta: `AI Master${item.model ? ` • ${item.model}` : ''}`,
      });
    } else if (item.status === 'failed') {
      rows.push({
        id: `e:${item.id}`,
        ts: item.answeredAt ?? item.askedAt,
        role: 'system',
        text: `Не удалось ответить: ${item.error ?? 'unknown_error'}`,
        meta: 'System',
      });
    } else {
      rows.push({
        id: `p:${item.id}`,
        ts: item.askedAt,
        role: 'system',
        text: 'Вопрос отправлен. Ждём ответ AI…',
        meta: 'Queue',
      });
    }
  }

  return rows.sort((a, b) => Date.parse(a.ts) - Date.parse(b.ts));
}

export function AiMasterPage() {
  const [insights, setInsights] = useState<AiMasterInsight[]>([]);
  const [qa, setQa] = useState<AiMasterQaItem[]>([]);
  const [question, setQuestion] = useState('');
  const [busy, setBusy] = useState(false);
  const [info, setInfo] = useState('');
  const [stickToBottom, setStickToBottom] = useState(true);
  const chatWindowRef = useRef<HTMLDivElement | null>(null);

  async function refresh() {
    const next = await getAiMasterSnapshot(200);
    setInsights(next.insights ?? []);
    setQa(next.qa ?? []);
  }

  useEffect(() => {
    refresh().catch(() => {
      setInfo('Could not load AI Master chat.');
    });

    const timer = setInterval(() => {
      refresh().catch(() => undefined);
    }, 10000);

    return () => clearInterval(timer);
  }, []);

  const messages = useMemo(() => toChatMessages(insights, qa), [insights, qa]);

  useEffect(() => {
    const el = chatWindowRef.current;
    if (!el || !stickToBottom) return;
    el.scrollTop = el.scrollHeight;
  }, [messages, stickToBottom]);

  function handleChatScroll() {
    const el = chatWindowRef.current;
    if (!el) return;
    const gap = el.scrollHeight - el.scrollTop - el.clientHeight;
    setStickToBottom(gap < 80);
  }

  async function handleAsk() {
    const text = question.trim();
    if (!text) return;
    setBusy(true);
    setInfo('Отправляю вопрос...');
    try {
      await submitAiMasterQuestion(text);
      setQuestion('');
      setInfo('Вопрос отправлен. Ответ придёт в чат и Telegram.');
      setStickToBottom(true);
      await refresh();
    } catch (error) {
      setInfo(friendlyErrorMessage(error, 'Не удалось отправить вопрос.'));
    } finally {
      setBusy(false);
    }
  }

  const answeredCount = useMemo(() => qa.filter((x) => x.status === 'answered').length, [qa]);
  const pendingCount = useMemo(() => qa.filter((x) => x.status === 'pending').length, [qa]);

  return (
    <main className="terminal-layout">
      <Card
        title="AI Master"
        className="full-width terminal-card"
        actions={(
          <div className="actions-row">
            <Badge tone="neutral">reports: {insights.length}</Badge>
            <Badge tone={pendingCount > 0 ? 'danger' : 'success'}>pending: {pendingCount}</Badge>
            <Badge tone="success">answered: {answeredCount}</Badge>
            <Button variant="secondary" onClick={() => refresh()} disabled={busy}>Refresh</Button>
          </div>
        )}
      >
        <div className="muted" style={{ marginBottom: '0.6rem' }}>
          Чат AI ассистента: сюда приходят daily-отчёты, здесь же можно задать вопрос и просмотреть историю переписки.
        </div>

        <div className="ai-chat-shell">
          <div className="ai-chat-window" ref={chatWindowRef} onScroll={handleChatScroll}>
            {messages.length === 0 ? (
              <p className="muted">Пока нет сообщений. Первый daily insight появится автоматически.</p>
            ) : (
              messages.map((msg) => (
                <div key={msg.id} className={`ai-chat-row ai-chat-row--${msg.role}`}>
                  <div className={`ai-chat-bubble ai-chat-bubble--${msg.role}`}>
                    <div className="ai-chat-meta">{msg.meta ?? (msg.role === 'assistant' ? 'AI Master' : msg.role === 'user' ? 'You' : 'System')} • {formatDate(msg.ts)}</div>
                    <div className="ai-chat-text">{msg.text}</div>
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="ai-chat-composer">
            <textarea
              id="ai-master-question"
              className="rules-input ai-chat-input"
              value={question}
              rows={3}
              placeholder="Например: Как оптимизировать текущие открытые позиции и снизить fee burn?"
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  void handleAsk();
                }
              }}
            />
            <div className="actions-row" style={{ justifyContent: 'space-between' }}>
              <span className="muted">{info}</span>
              <Button onClick={() => { void handleAsk(); }} disabled={busy || question.trim().length === 0}>Send</Button>
            </div>
          </div>
        </div>
      </Card>
    </main>
  );
}
