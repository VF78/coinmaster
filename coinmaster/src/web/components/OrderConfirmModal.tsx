import { useCallback, useEffect, useState } from 'react';
import { Badge } from './Badge';
import { Button } from './Button';
import { formatMoney, formatNumber } from '../lib/format';
import type { PlaceOrderPayload, PlaceOrderResponse, RiskCheckResponse } from '../lib/api';
import { placeOrder, getRiskCheck } from '../lib/api';

export interface OrderDraft {
  symbol: string;
  side: 'buy' | 'sell';
  price: number;
  size: number;
  leverage?: number;
  reduceOnly?: boolean;
  stopLoss?: number;
  takeProfit?: number;
}

interface Props {
  draft: OrderDraft;
  onClose: () => void;
  onSuccess: () => void;
}

type ModalStep = 'preflight' | 'confirm' | 'submitting' | 'success' | 'error';

const ERROR_MESSAGES: Record<string, string> = {
  auth_required: 'Authentication required. Check your OWNER_AUTH_TOKEN.',
  insufficient_balance: 'Insufficient balance to place this order.',
  max_notional_exceeded: 'Order exceeds maximum notional USDC limit.',
  leverage_limit_exceeded: 'Leverage exceeds the configured maximum.',
  daily_loss_limit_exceeded: 'Daily loss limit reached. Trading is blocked for today.',
  dd_lock_active: 'Daily drawdown lock is active. New entry orders are blocked until you reset the lock.',
  manual_confirmation_required: 'Manual confirmation is required (internal error).',
  rate_limited: 'Rate limited by exchange. Wait a moment and retry.',
  invalid_params: 'Invalid order parameters. Check price and size.',
  exchange_error: 'Exchange returned an error. See details below.',
};

export function OrderConfirmModal({ draft, onClose, onSuccess }: Props) {
  const [step, setStep] = useState<ModalStep>('preflight');
  const [risk, setRisk] = useState<RiskCheckResponse | null>(null);
  const [result, setResult] = useState<PlaceOrderResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [clientOrderId] = useState(() => `ui-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`);
  const [idempotent, setIdempotent] = useState(false);

  const notional = draft.price * draft.size;
  const sideLabel = draft.side === 'buy' ? 'LONG' : 'SHORT';
  const sideTone = draft.side === 'buy' ? 'success' : 'danger';

  // Preflight risk check
  useEffect(() => {
    let cancelled = false;
    getRiskCheck()
      .then((r) => {
        if (cancelled) return;
        setRisk(r);
        setStep('confirm');
      })
      .catch((e) => {
        if (cancelled) return;
        // If risk check fails, still allow confirm (fail-open matches server behavior)
        setRisk(null);
        setStep('confirm');
      });
    return () => { cancelled = true; };
  }, []);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  const handleConfirm = useCallback(async () => {
    setStep('submitting');
    try {
      const payload: PlaceOrderPayload = {
        symbol: draft.symbol,
        side: draft.side,
        price: draft.price,
        size: draft.size,
        leverage: draft.leverage,
        reduceOnly: draft.reduceOnly,
        clientOrderId,
        confirm: true,
      };
      const resp = await placeOrder(payload);
      setResult(resp);
      if (resp.idempotent) {
        setIdempotent(true);
      }
      if (resp.ok) {
        setStep('success');
      } else {
        setErrorMsg(resp.error || ERROR_MESSAGES[resp.errorCode || ''] || 'Unknown error');
        setStep('error');
      }
    } catch (e: any) {
      // Try to parse JSON error from response
      let parsed: any = null;
      if (e?.response) {
        try { parsed = await e.response.json(); } catch {}
      }
      if (parsed) {
        setResult(parsed);
        setErrorMsg(parsed.error || ERROR_MESSAGES[parsed.errorCode || ''] || e.message);
      } else {
        setErrorMsg(e.message || 'Network error');
      }
      setStep('error');
    }
  }, [draft, clientOrderId]);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <header className="modal-header">
          <h2 className="modal-title">
            {step === 'success' ? '✅ Order Placed' : step === 'error' ? '❌ Order Failed' : 'Confirm Order'}
          </h2>
          <button className="modal-close" onClick={onClose}>✕</button>
        </header>

        {/* Preflight / Loading */}
        {step === 'preflight' && (
          <div className="modal-body">
            <p className="muted">Running pre-flight risk checks…</p>
          </div>
        )}

        {/* Confirm step */}
        {step === 'confirm' && (
          <div className="modal-body">
            {/* Order details */}
            <div className="order-summary">
              <div className="order-summary__row">
                <span className="order-summary__label">Symbol</span>
                <span className="order-summary__value">{draft.symbol}</span>
              </div>
              <div className="order-summary__row">
                <span className="order-summary__label">Side</span>
                <span className="order-summary__value"><Badge tone={sideTone}>{sideLabel}</Badge></span>
              </div>
              <div className="order-summary__row">
                <span className="order-summary__label">Price</span>
                <span className="order-summary__value">{formatMoney(draft.price)}</span>
              </div>
              <div className="order-summary__row">
                <span className="order-summary__label">Size</span>
                <span className="order-summary__value">{formatNumber(draft.size)} {draft.symbol}</span>
              </div>
              {draft.leverage !== undefined && (
                <div className="order-summary__row">
                  <span className="order-summary__label">Leverage</span>
                  <span className="order-summary__value">{formatNumber(draft.leverage)}x</span>
                </div>
              )}
              {draft.stopLoss !== undefined && (
                <div className="order-summary__row">
                  <span className="order-summary__label">Stop Loss</span>
                  <span className="order-summary__value">{formatMoney(draft.stopLoss)}</span>
                </div>
              )}
              {draft.takeProfit !== undefined && (
                <div className="order-summary__row">
                  <span className="order-summary__label">Take Profit</span>
                  <span className="order-summary__value">{formatMoney(draft.takeProfit)}</span>
                </div>
              )}
            </div>

            {/* Risk summary */}
            <div className="risk-summary">
              <h3 className="risk-summary__title">Risk Summary</h3>
              <div className="order-summary__row">
                <span className="order-summary__label">Notional</span>
                <span className="order-summary__value">{formatMoney(notional)}</span>
              </div>
              {draft.leverage !== undefined && (
                <div className="order-summary__row">
                  <span className="order-summary__label">Leverage ratio</span>
                  <span className="order-summary__value">{formatNumber(draft.leverage)}x</span>
                </div>
              )}
              {risk && (
                <>
                  <div className="order-summary__row">
                    <span className="order-summary__label">Account equity</span>
                    <span className="order-summary__value">{formatMoney(risk.equityUsd)}</span>
                  </div>
                  <div className="order-summary__row">
                    <span className="order-summary__label">Portfolio leverage</span>
                    <span className="order-summary__value">{formatNumber(risk.portfolioLeverage)}x</span>
                  </div>
                  <div className="order-summary__row">
                    <span className="order-summary__label">Daily drawdown</span>
                    <span className="order-summary__value">
                      <Badge tone={risk.dailyDDPct >= risk.dailyDDLimitPct ? 'danger' : risk.dailyDDPct > risk.dailyDDLimitPct * 0.7 ? 'neutral' : 'success'}>
                        {formatNumber(risk.dailyDDPct)}% / {formatNumber(risk.dailyDDLimitPct)}% limit
                      </Badge>
                    </span>
                  </div>
                  <div className="order-summary__row">
                    <span className="order-summary__label">Impact on equity</span>
                    <span className="order-summary__value">
                      {risk.equityUsd > 0 ? formatNumber((notional / risk.equityUsd) * 100) + '% of equity' : '—'}
                    </span>
                  </div>
                  {risk.blocks.length > 0 && (
                    <div className="risk-blocks">
                      ⚠️ Risk gates blocking: {risk.blocks.join(', ')}
                    </div>
                  )}
                </>
              )}
              {!risk && <p className="muted">Risk check unavailable (will be validated server-side)</p>}
            </div>

            <div className="modal-actions">
              <Button variant="secondary" onClick={onClose} fullWidth>Cancel</Button>
              <Button
                variant={draft.side === 'buy' ? 'primary' : 'danger'}
                onClick={handleConfirm}
                fullWidth
                disabled={risk?.blocks?.length ? true : false}
              >
                {risk?.blocks?.length ? 'Blocked by risk gates' : `Confirm ${sideLabel} ${draft.symbol}`}
              </Button>
            </div>
          </div>
        )}

        {/* Submitting */}
        {step === 'submitting' && (
          <div className="modal-body">
            <p className="muted">Submitting order to Hyperliquid…</p>
          </div>
        )}

        {/* Success */}
        {step === 'success' && result && (
          <div className="modal-body">
            {idempotent && (
              <div className="idempotent-notice">
                ℹ️ Already submitted — this is a duplicate confirmation.
              </div>
            )}
            <div className="order-summary">
              <div className="order-summary__row">
                <span className="order-summary__label">Order ID</span>
                <span className="order-summary__value mono">{result.orderId ?? '—'}</span>
              </div>
              <div className="order-summary__row">
                <span className="order-summary__label">Client ID</span>
                <span className="order-summary__value mono">{result.clientOrderId ?? '—'}</span>
              </div>
              <div className="order-summary__row">
                <span className="order-summary__label">Status</span>
                <span className="order-summary__value"><Badge tone="success">{result.status ?? 'submitted'}</Badge></span>
              </div>
              <div className="order-summary__row">
                <span className="order-summary__label">Entry price</span>
                <span className="order-summary__value">{formatMoney(draft.price)}</span>
              </div>
              {draft.stopLoss !== undefined && (
                <div className="order-summary__row">
                  <span className="order-summary__label">Stop Loss</span>
                  <span className="order-summary__value">{formatMoney(draft.stopLoss)}</span>
                </div>
              )}
              {draft.takeProfit !== undefined && (
                <div className="order-summary__row">
                  <span className="order-summary__label">Take Profit</span>
                  <span className="order-summary__value">{formatMoney(draft.takeProfit)}</span>
                </div>
              )}
            </div>
            <div className="modal-actions">
              <Button variant="primary" onClick={() => { onSuccess(); onClose(); }} fullWidth>
                Back to Dashboard
              </Button>
            </div>
          </div>
        )}

        {/* Error */}
        {step === 'error' && (
          <div className="modal-body">
            <div className="error-notice">
              <p className="error-notice__code">
                {result?.errorCode && <Badge tone="danger">{result.errorCode}</Badge>}
              </p>
              <p className="error-notice__msg">
                {ERROR_MESSAGES[result?.errorCode || ''] || errorMsg}
              </p>
              {errorMsg && errorMsg !== ERROR_MESSAGES[result?.errorCode || ''] && (
                <p className="muted">{errorMsg}</p>
              )}
            </div>
            <div className="modal-actions">
              <Button variant="secondary" onClick={onClose} fullWidth>Dismiss</Button>
              <Button variant="primary" onClick={() => setStep('confirm')} fullWidth>Try Again</Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
