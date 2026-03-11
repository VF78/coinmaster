import { applyBybitConnectionPatch, getBybitConnectionSettings, getMaskedBybitConnectionSettings } from '../src/integrations/readOnlyExchanges/service.js';
import { normalizeBybitExecutionToFill, type BybitExecutionRow } from '../src/integrations/readOnlyExchanges/bybitReadOnlyConnector.js';
import type { AppSettings } from '../src/shared/dto.js';

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

function makeSettings(): AppSettings {
  return {
    depositUsd: 0,
    telegramNotify: {
      botToken: '',
      chatId: '',
      notifyOpen: false,
      notifyTp: false,
      notifySl: false,
      notifyManualConfirm: false,
      notifyDailyAnalytics: false,
      notifySignalRejected: false,
      notifyOrderRejected: false,
      notifyPositionClosed: false,
    },
    tradingRules: {
      coins: [],
      entryTf: '15m',
      exitTf: '1h',
      entryTimeframes: ['15m'],
      emergencyExitTimeframes: ['1h'],
      engulfingLookbackCandles: 5,
      fvgRetrace: 0.5,
      fvgMinWidthPct: 0.3,
      maxLeverage: 5,
      dailyDrawdown: 5,
      tpPct: 2,
      slPct: 1,
      tpLevels: [3],
      exitClosePct: 50,
      autoConfirm: false,
    },
    externalExchanges: {
      bybit: {
        mode: 'off',
        apiKey: '',
        apiSecret: '',
        accountType: 'UNIFIED',
        categories: ['linear'],
      },
    },
  };
}

console.log('\n── Read-only exchanges invariants ──');

console.log('\nCase 1: apply patch preserves and normalizes settings');
{
  const settings = makeSettings();
  applyBybitConnectionPatch(settings, {
    mode: 'read_only',
    apiKey: '  test-key-123456  ',
    apiSecret: '  secret-abcdef  ',
    accountType: 'SPOT',
    categories: ['linear', 'spot', 'spot'],
  });
  const bybit = getBybitConnectionSettings(settings);
  assert(bybit.mode === 'read_only', 'mode set to read_only');
  assert(bybit.apiKey === 'test-key-123456', 'api key trimmed');
  assert(bybit.apiSecret === 'secret-abcdef', 'api secret trimmed');
  assert(bybit.accountType === 'SPOT', 'account type preserved');
  assert(bybit.categories.length === 2 && bybit.categories.includes('linear') && bybit.categories.includes('spot'), 'categories deduped');
}

console.log('\nCase 2: masked settings never expose raw secrets');
{
  const settings = makeSettings();
  applyBybitConnectionPatch(settings, {
    mode: 'read_only',
    apiKey: 'abc123456789',
    apiSecret: 'def987654321',
  });
  const masked = getMaskedBybitConnectionSettings(settings);
  assert(masked.hasApiKey === true, 'masked payload says api key is present');
  assert(masked.hasApiSecret === true, 'masked payload says api secret is present');
  assert(masked.apiKeyMasked !== 'abc123456789', 'api key is masked');
  assert(masked.apiSecretMasked !== 'def987654321', 'api secret is masked');
}

console.log('\nCase 3: Bybit execution normalization adds source attribution');
{
  const row: BybitExecutionRow = {
    symbol: 'BTCUSDT',
    side: 'Sell',
    execPrice: '62500.5',
    execQty: '0.25',
    execTime: '1710000000000',
    execFee: '-1.25',
    execPnl: '15.5',
    closedSize: '0.25',
    execId: 'exec-1',
  };
  const fill = normalizeBybitExecutionToFill('linear', row);
  assert(Boolean(fill), 'row normalized to fill');
  assert(fill?.id === 'bybit:linear:exec-1', 'fill id is prefixed by exchange/category');
  const raw = fill?.raw as { sourceExchange?: string; dir?: string } | undefined;
  assert(raw?.sourceExchange === 'bybit', 'sourceExchange=bybit stored in raw payload');
  assert(raw?.dir === 'close trade', 'closed fill classified as close trade');
}

console.log('\nCase 4: invalid execution rows are ignored safely');
{
  const invalid = normalizeBybitExecutionToFill('linear', {
    symbol: '',
    side: 'Sell',
    execPrice: '0',
    execQty: '0',
    execTime: '0',
  });
  assert(invalid === null, 'invalid row returns null');
}

console.log(`\nResult: ${passed} passed, ${failed} failed`);
if (failed > 0) process.exit(1);
