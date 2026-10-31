"""Exact read-only cache of authoritative native signed funding audit totals.

Never posts money or modifies the journal/schema. The full original sorted
audit and per-asset Decimal addition order are retained whenever refreshed.
"""
from decimal import Decimal,getcontext,localcontext

class NativeSignedFundingReader:
    def __init__(self,journal):
        self.journal=journal
        self._connection=None
        self._revision=None
        self._rows=None
        self._totals={}

    @staticmethod
    def _context_key(ctx):
        return (ctx.prec,ctx.rounding,ctx.Emin,ctx.Emax,ctx.capitals,ctx.clamp,
                tuple(ctx.traps.items()))

    @staticmethod
    def _sum(rows,instrument_id,ctx):
        signaled=()
        try:
            # Identical Decimal operations/settings, with signal replay so cache
            # hits preserve the original sum's flags as well as its numeric value.
            with localcontext(ctx) as calculation:
                calculation.clear_flags()
                try:
                    value=sum((Decimal(row[5]) for row in rows if row[1]==instrument_id),Decimal(0))
                finally:
                    signaled=tuple(signal for signal,raised in calculation.flags.items() if raised)
        finally:
            for signal in signaled:ctx.flags[signal]=True
        return value,signaled

    def __call__(self,instrument_id):
        if self.journal is None:
            return Decimal(0)
        connection=self.journal.db
        ctx=getcontext()
        asset=str(instrument_id)
        # total_changes does not roll back. Never reuse a transactional view,
        # including SAVEPOINT/ROLLBACK TO, as a stable committed cache.
        if connection.in_transaction:
            self._revision=None;self._rows=None;self._totals={}
            return self._sum(self.journal.funding_cash_audit(),asset,ctx)[0]
        # Own writer commits: total_changes. Other connection commits:
        # data_version. Connection identity also protects close/reopen.
        version=connection.execute("PRAGMA data_version").fetchone()[0]
        revision=(connection.total_changes,version,self._context_key(ctx))
        if connection is not self._connection or revision!=self._revision:
            self._rows=self.journal.funding_cash_audit()
            self._connection=connection;self._revision=revision;self._totals={}
        if asset not in self._totals:
            self._totals[asset]=self._sum(self._rows,asset,ctx)
        value,signaled=self._totals[asset]
        for signal in signaled:ctx.flags[signal]=True
        return value
