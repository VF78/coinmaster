"""Offline 1.231 execution selection and multi-currency USDC account fixtures."""
import json
from decimal import Decimal
from pathlib import Path

import pytest
from nautilus_trader.accounting.accounts.margin import MarginAccount
from nautilus_trader.adapters.hyperliquid import HyperliquidLiveExecClientFactory
from nautilus_trader.adapters.hyperliquid.config import HyperliquidExecClientConfig
from nautilus_trader.adapters.sandbox.config import SandboxExecutionClientConfig
from nautilus_trader.core.uuid import UUID4
from nautilus_trader.model.currencies import USDC
from nautilus_trader.model.enums import AccountType
from nautilus_trader.model.events import AccountState
from nautilus_trader.model.identifiers import AccountId
from nautilus_trader.model.objects import AccountBalance, MarginBalance, Money

from coinmaster.ops.hl_native_account import native_live_usdc_projection, native_usdc_balances
from coinmaster.ops.hl_sandbox_money import SandboxLiveExecClientFactory as HyperliquidUsdcSandboxFactory
from coinmaster.ops.hyperliquid_testnet import (
    assert_native_testnet_only, execution_factory_for_mode, hyperliquid_testnet_node_config,
)
from coinmaster.ops.hyperliquid_testnet_worker import TestnetWorker as Worker
from coinmaster.ops.stage_g_config import ConfigurationError, load_testnet_instance_config


def _native_account(total='100', locked='20', free='80', *, include_usdc=True):
    balances = [AccountBalance(Money(total, USDC), Money(locked, USDC), Money(free, USDC))] if include_usdc else []
    margins = [MarginBalance(Money('15', USDC), Money('15', USDC), None)]
    event = AccountState(AccountId('HYPERLIQUID-master'), AccountType.MARGIN, None, True,
                         balances, margins, {}, UUID4(), 1, 1)
    return MarginAccount(event)


def test_native_multicurrency_usdc_balances_preserve_pending_lock_and_do_not_infer_equity():
    account = _native_account()
    assert account.base_currency is None
    assert native_usdc_balances(account) == {
        'total': Decimal('100'), 'free': Decimal('80'), 'locked': Decimal('20'),
    }
    # Adapter-shaped account-wide margin uses one totalMarginUsed source for
    # both fields. This fixture tests getters, not actual venue economics.
    assert account.account_margins()[USDC].initial.as_decimal() == Decimal('15')
    assert account.account_margins()[USDC].maintenance.as_decimal() == Decimal('15')
    projection = native_live_usdc_projection(account)
    assert tuple(Decimal(projection[key]) for key in ('native_balance_total', 'native_free', 'native_locked')) == (Decimal('100'), Decimal('80'), Decimal('20'))
    assert tuple(Decimal(projection[key]) for key in ('native_margin_initial', 'native_margin_maintenance')) == (Decimal('15'), Decimal('15'))
    assert projection['cash'] is None and projection['equity'] is None
    assert projection['money_state'] == 'UNKNOWN_NATIVE_HL_ACCOUNT_VALUE_UNMAPPED'
    assert native_usdc_balances(_native_account('100', '0', '100'))['locked'] == 0
    with pytest.raises(ValueError, match='NATIVE_USDC_TOTAL_UNKNOWN'):
        native_usdc_balances(_native_account(include_usdc=False))


def test_both_profiles_select_exactly_one_pinned_native_factory_and_no_secret_value(monkeypatch):
    monkeypatch.setenv('HYPERLIQUID_PK', 'must-not-be-read')
    sandbox = hyperliquid_testnet_node_config(trader_id='CM-SANDBOX')
    live = hyperliquid_testnet_node_config(trader_id='CM-LIVE', execution_mode='live')
    assert set(sandbox.exec_clients) == {'SANDBOX'}
    assert isinstance(sandbox.exec_clients['SANDBOX'], SandboxExecutionClientConfig)
    assert execution_factory_for_mode('sandbox') == ('SANDBOX', HyperliquidUsdcSandboxFactory)
    assert_native_testnet_only(sandbox)
    assert set(live.exec_clients) == {'HYPERLIQUID-LIVE'}
    assert isinstance(live.exec_clients['HYPERLIQUID-LIVE'], HyperliquidExecClientConfig)
    assert live.exec_clients['HYPERLIQUID-LIVE'].private_key is None
    assert execution_factory_for_mode('live') == ('HYPERLIQUID-LIVE', HyperliquidLiveExecClientFactory)
    assert_native_testnet_only(live, 'live')
    with pytest.raises(RuntimeError, match='SINGLE_NATIVE_ROUTE'):
        assert_native_testnet_only(live, 'sandbox')
    with pytest.raises(ValueError, match='UNKNOWN_EXECUTION_MODE'):
        execution_factory_for_mode('other')


def test_live_identity_is_isolated_and_worker_refuses_before_opening_state(tmp_path):
    source = Path(__file__).resolve().parents[1] / 'configs/hl-stageg-testnet.instance.json'
    document = json.loads(source.read_text())
    document.update(instance_id='hl-stageg-live', mode='live', state_db='/var/lib/coinmaster-hl-stageg-live/hl-stageg-live.sqlite',
                    signal_warmup_manifest='/var/lib/coinmaster-hl-stageg-live/data/current/manifest.json')
    path = tmp_path / 'live.json'
    path.write_text(json.dumps(document))
    instance = load_testnet_instance_config(path)
    assert instance.mode == 'live'
    assert instance.state_db != load_testnet_instance_config(source).state_db
    with pytest.raises(RuntimeError, match='HL_LIVE_ROUTE_NOT_APPROVED'):
        Worker({'COINMASTER_HL_TESTNET_INSTANCE_CONFIG': str(path)})
    document['state_db'] = '/var/lib/coinmaster-hl-stageg-testnet/hl-stageg-testnet.sqlite'
    path.write_text(json.dumps(document))
    with pytest.raises(ConfigurationError, match='UNSAFE_TESTNET_STATE_DB_PATH'):
        load_testnet_instance_config(path)
