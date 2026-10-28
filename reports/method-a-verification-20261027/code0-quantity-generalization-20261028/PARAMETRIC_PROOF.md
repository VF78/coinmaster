# Quantity-independent CODE0 proof (conditional, engine-free)

New direct human authorization: «Разрешаю обобщение, native0», exact receipt
OWNER_APPROVAL.json. This explicitly resolves the old quantity-removal rejection;
AUTO_REVIEW_REJECTION.json from the prior stage remains historical evidence.

Let B>=0 and S=-h<=0 be ACTUAL native signed positions, and Q<=B be the sole
known ACKed BTC TP's actual working leaves. x in[0,Q] is OLD BTC TP execution;
z in[0,h] is NEW SOL reduction execution. B,h,Q are native lot quantities,
not tuning parameters. E,H,Pb,Ps and the five frozen scenario shocks are known
from the same actual snapshot/frame. Old TP has exact signed nonnegative cost
kb=Pb-limit+limit*knownMakerFee; its minimum-lot commission must lie exactly on
the native quote Money lattice. The new LIMIT IOC enforces an upper bound ks
including maximum linear fee and conservative minimum-lot fee rounding. Funding
is known0; signs cannot cross; all scenario notionals stay in the same first
venue tier with zero deductions, as checked before proof. Unsupported cases
remain UNKNOWN/DENY. Existing one-old-order/ACK/protection guards are unchanged.

For each scenario k, use ONLY the existing evaluate law on
(B-x,-h+z,E-kb*x-ks*z,H,Pb,Ps). Because signs and margin coefficients are fixed,
scenario PnL, exit reserves, paid costs, IM/MM slack and cushion are affine in
(x,z). Zero shock supplies a nonnegative exit-cost loss, so signed deficit F
is the maximum of the five affine scenario deficits. F is convex. Consequently
its maximum over[0,Q]x[0,h] is attained at a corner. The SAME old-order baseline
is max(F(0,0),F(Q,0)); full new-SOL edge is bounded by max(F(0,h),F(Q,h)). If
both full-edge corners are safe and every route corner is <=that same baseline,
convex combinations prove all zero/partial/full outcomes no worse than it.
Each scenario's margin slack and cash cushion are affine too; their corner
minimum proves the corresponding whole-rectangle condition. No expected fill,
pending hedge or artificial capital is credited. Native lot outcomes are a
subset of this continuous domain. Additional price/feature/peak changes require
a fresh proof; the existing sole-IOC drain validates its frozen live frame.

The implementation continues using the pre-existing exact tier_partition_envelope
and evaluate, rather than introducing an economic simulator or brute grid.
For BTC trim, old/new BTC fills share clipped inventory and different costs:
the existing descending-cost frontier/partitioner covers its piecewise-affine
quantity cells. This proposal does not silently apply an independent 2D
rectangle to overlapping same-leg fills. Full-held close candidates remain
the existing bounded choice policy; no economic optimizer or new strategy.

First-tier guard, maker/taker/fee-affinity, positive actual cushion, actual
BREACH/margin, native ownership/ACK, dormant old SOL TP/STOP, original deadline,
protection resize drain and ordinary admission/DD50 all remain unchanged.
The theorem has no BTC1/SOL132.9 numerical boundary: quantity bounds arise from
ACTUAL inventory, native leaves and verified tier/scenario conditions. It
proves the fixed scenario risk model, not live gaps, fill completion, native
lifecycle, PnL, financial qualification or final ROI. Native/prefix/full0.
