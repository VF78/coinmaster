import { AI_MASTER_LIMITS, applyAiMasterQaAnswer, buildAiMasterInsight, buildAiMasterQaQuestion, pruneAiMasterCollections } from '../src/server/aiMaster.js';
import type { AiMasterInsight, AiMasterQaItem } from '../src/shared/dto.js';

let passed = 0;
let failed = 0;

function assert(condition: boolean, message: string): void {
  if (condition) {
    passed += 1;
    console.log(`  ✓ ${message}`);
  } else {
    failed += 1;
    console.error(`  ✗ ${message}`);
  }
}

console.log('\n── AI Master invariants ──');

console.log('\nCase 1: insight payload keeps observability metadata and guardrails');
{
  const created = buildAiMasterInsight({
    id: 'aii-test',
    text: 'x'.repeat(AI_MASTER_LIMITS.maxInsightTextChars + 50),
    model: 'openai-codex/gpt-5.3-codex',
    source: 'telegram_daily',
    promptVersion: 'v2',
    runId: 'run-123',
    worker: 'openclaw-daily',
    dayKey: 'bad-day-key',
    fallbackDayKey: '2026-03-10',
    createdAt: '2026-03-10T12:00:00.000Z',
    latencyMs: 1532,
    timeoutMs: 45000,
    promptChars: 8000,
    responseChars: 12050,
    fallbackUsed: true,
  });

  assert(created.ok, 'insight is created');
  if (created.ok) {
    assert(created.insight.dayKey === '2026-03-10', 'invalid dayKey falls back to local day key');
    assert(created.insight.status === 'fallback', 'fallbackUsed marks insight as fallback');
    assert(created.insight.truncated === true, 'oversized insight text is marked truncated');
    assert(created.insight.latencyMs === 1532, 'latency is stored');
    assert(created.insight.timeoutMs === 45000, 'timeout is stored');
    assert(created.insight.promptChars === 8000, 'promptChars is stored');
  }
}

console.log('\nCase 2: question payload is truncated but accepted');
{
  const created = buildAiMasterQaQuestion({
    id: 'aiq-test',
    question: 'q'.repeat(AI_MASTER_LIMITS.maxQaQuestionChars + 20),
    askedAt: '2026-03-10T12:01:00.000Z',
  });
  assert(created.ok, 'qa question is created');
  if (created.ok) {
    assert(created.item.status === 'pending', 'new question is pending');
    assert(created.item.truncated === true, 'oversized question is marked truncated');
    assert(created.item.promptChars === AI_MASTER_LIMITS.maxQaQuestionChars + 20, 'original prompt length preserved for observability');
  }
}

console.log('\nCase 3: fallback answer records success with fallbackUsed');
{
  const item: AiMasterQaItem = {
    id: 'aiq-answer',
    question: 'What changed?',
    status: 'pending',
    askedAt: '2026-03-10T12:02:00.000Z',
  };
  const updated = applyAiMasterQaAnswer(item, {
    fallbackMessage: 'Временно не удалось получить ответ модели. Используй deterministic daily summary.',
    model: 'anthropic/claude-sonnet-4-6',
    runId: 'qa-run-1',
    worker: 'openclaw-qa',
    latencyMs: 21000,
    timeoutMs: 20000,
    fallbackUsed: true,
    answeredAt: '2026-03-10T12:03:00.000Z',
  });
  assert(updated.ok, 'fallback answer applied');
  if (updated.ok) {
    assert(updated.item.status === 'answered', 'fallback message still counts as answered');
    assert(updated.item.fallbackUsed === true, 'fallbackUsed persisted');
    assert(Boolean(updated.item.answer), 'fallback answer text stored');
    assert(updated.item.runId === 'qa-run-1', 'runId stored for QA');
  }
}

console.log('\nCase 4: pruning keeps bounded history');
{
  const insights: AiMasterInsight[] = Array.from({ length: AI_MASTER_LIMITS.maxInsights + 10 }, (_, i) => ({
    id: `i-${i}`,
    dayKey: '2026-03-10',
    source: 'manual',
    text: `insight-${i}`,
    createdAt: '2026-03-10T12:00:00.000Z',
  }));
  const qa: AiMasterQaItem[] = Array.from({ length: AI_MASTER_LIMITS.maxQa + 10 }, (_, i) => ({
    id: `q-${i}`,
    question: `question-${i}`,
    status: 'pending',
    askedAt: '2026-03-10T12:00:00.000Z',
  }));
  pruneAiMasterCollections(insights, qa);
  assert(insights.length === AI_MASTER_LIMITS.maxInsights, 'insights collection is bounded');
  assert(qa.length === AI_MASTER_LIMITS.maxQa, 'qa collection is bounded');
}

console.log(`\nResult: ${passed} passed, ${failed} failed`);
if (failed > 0) process.exit(1);
