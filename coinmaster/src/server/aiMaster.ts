import type { AiMasterInsight, AiMasterQaItem } from '../shared/dto.js';

export const AI_MASTER_LIMITS = {
  maxInsights: 500,
  maxQa: 2000,
  maxInsightTextChars: 12_000,
  maxQaQuestionChars: 4_000,
  maxQaAnswerChars: 12_000,
  maxQaErrorChars: 2_000,
  maxSourceChars: 64,
  maxModelChars: 120,
  maxPromptVersionChars: 64,
  maxRunIdChars: 128,
  maxWorkerChars: 64,
  maxTimeoutMs: 600_000,
  maxLatencyMs: 600_000,
  maxPromptChars: 100_000,
  maxResponseChars: 100_000,
} as const;

function clampInt(value: unknown, max: number): number | undefined {
  const n = Number(value);
  if (!Number.isFinite(n) || n < 0) return undefined;
  return Math.min(max, Math.floor(n));
}

function trimString(value: unknown, max: number): string | undefined {
  const text = String(value ?? '').trim();
  if (!text) return undefined;
  return text.slice(0, max);
}

function normalizeDayKey(value: unknown, fallback: string): string {
  const dayKey = String(value ?? '').trim();
  return /^\d{4}-\d{2}-\d{2}$/.test(dayKey) ? dayKey : fallback;
}

export function pruneAiMasterCollections(insights: AiMasterInsight[], qa: AiMasterQaItem[]): void {
  if (insights.length > AI_MASTER_LIMITS.maxInsights) {
    insights.splice(0, insights.length - AI_MASTER_LIMITS.maxInsights);
  }
  if (qa.length > AI_MASTER_LIMITS.maxQa) {
    qa.splice(0, qa.length - AI_MASTER_LIMITS.maxQa);
  }
}

export function buildAiMasterInsight(input: {
  id: string;
  text: unknown;
  model?: unknown;
  source?: unknown;
  promptVersion?: unknown;
  runId?: unknown;
  worker?: unknown;
  dayKey?: unknown;
  fallbackDayKey: string;
  createdAt: string;
  latencyMs?: unknown;
  timeoutMs?: unknown;
  promptChars?: unknown;
  responseChars?: unknown;
  fallbackUsed?: unknown;
}): { ok: true; insight: AiMasterInsight } | { ok: false; error: string } {
  const rawText = String(input.text ?? '').trim();
  if (!rawText) return { ok: false, error: 'text_required' };

  const text = rawText.slice(0, AI_MASTER_LIMITS.maxInsightTextChars);
  const fallbackUsed = Boolean(input.fallbackUsed);
  const responseChars = clampInt(input.responseChars, AI_MASTER_LIMITS.maxResponseChars) ?? rawText.length;

  return {
    ok: true,
    insight: {
      id: input.id,
      dayKey: normalizeDayKey(input.dayKey, input.fallbackDayKey),
      source: trimString(input.source, AI_MASTER_LIMITS.maxSourceChars) ?? 'manual',
      text,
      model: trimString(input.model, AI_MASTER_LIMITS.maxModelChars),
      promptVersion: trimString(input.promptVersion, AI_MASTER_LIMITS.maxPromptVersionChars),
      runId: trimString(input.runId, AI_MASTER_LIMITS.maxRunIdChars),
      worker: trimString(input.worker, AI_MASTER_LIMITS.maxWorkerChars),
      status: fallbackUsed ? 'fallback' : 'success',
      latencyMs: clampInt(input.latencyMs, AI_MASTER_LIMITS.maxLatencyMs),
      timeoutMs: clampInt(input.timeoutMs, AI_MASTER_LIMITS.maxTimeoutMs),
      promptChars: clampInt(input.promptChars, AI_MASTER_LIMITS.maxPromptChars),
      responseChars,
      fallbackUsed,
      truncated: rawText.length > text.length,
      createdAt: input.createdAt,
    },
  };
}

export function buildAiMasterQaQuestion(input: {
  id: string;
  question: unknown;
  askedAt: string;
}): { ok: true; item: AiMasterQaItem } | { ok: false; error: string } {
  const rawQuestion = String(input.question ?? '').trim();
  if (!rawQuestion) return { ok: false, error: 'question_required' };

  const question = rawQuestion.slice(0, AI_MASTER_LIMITS.maxQaQuestionChars);
  return {
    ok: true,
    item: {
      id: input.id,
      question,
      status: 'pending',
      askedAt: input.askedAt,
      promptChars: rawQuestion.length,
      truncated: rawQuestion.length > question.length,
    },
  };
}

export function applyAiMasterQaAnswer(item: AiMasterQaItem, input: {
  answer?: unknown;
  error?: unknown;
  model?: unknown;
  runId?: unknown;
  worker?: unknown;
  latencyMs?: unknown;
  timeoutMs?: unknown;
  promptChars?: unknown;
  responseChars?: unknown;
  fallbackUsed?: unknown;
  fallbackMessage?: unknown;
  answeredAt: string;
}): { ok: true; item: AiMasterQaItem } | { ok: false; error: string } {
  const rawAnswer = String(input.answer ?? '').trim();
  const rawFallback = String(input.fallbackMessage ?? '').trim();
  const rawError = String(input.error ?? '').trim();
  const answerSource = rawAnswer || rawFallback;

  if (!answerSource && !rawError) return { ok: false, error: 'answer_or_error_required' };

  item.model = trimString(input.model, AI_MASTER_LIMITS.maxModelChars);
  item.runId = trimString(input.runId, AI_MASTER_LIMITS.maxRunIdChars);
  item.worker = trimString(input.worker, AI_MASTER_LIMITS.maxWorkerChars);
  item.answeredAt = input.answeredAt;
  item.latencyMs = clampInt(input.latencyMs, AI_MASTER_LIMITS.maxLatencyMs);
  item.timeoutMs = clampInt(input.timeoutMs, AI_MASTER_LIMITS.maxTimeoutMs);
  item.promptChars = clampInt(input.promptChars, AI_MASTER_LIMITS.maxPromptChars) ?? item.promptChars;

  if (answerSource) {
    const answer = answerSource.slice(0, AI_MASTER_LIMITS.maxQaAnswerChars);
    item.status = 'answered';
    item.answer = answer;
    item.responseChars = clampInt(input.responseChars, AI_MASTER_LIMITS.maxResponseChars) ?? answerSource.length;
    item.fallbackUsed = Boolean(input.fallbackUsed) || Boolean(rawFallback && !rawAnswer);
    item.truncated = item.truncated || answerSource.length > answer.length;
    item.error = undefined;
    return { ok: true, item };
  }

  item.status = 'failed';
  item.answer = undefined;
  item.responseChars = clampInt(input.responseChars, AI_MASTER_LIMITS.maxResponseChars);
  item.fallbackUsed = Boolean(input.fallbackUsed);
  item.error = (rawError || 'qa_answer_failed').slice(0, AI_MASTER_LIMITS.maxQaErrorChars);
  return { ok: true, item };
}
