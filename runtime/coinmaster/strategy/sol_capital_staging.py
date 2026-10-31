"""Pure variant-A capital normalization and post-admission child quantity."""
from decimal import Decimal

BASE_SEED=Decimal("10000")
BASE_PARENT_CEILING=Decimal("30000000")
BASE_SOL_CHILD=Decimal("1000")


def funded_scale(initial_funded_seed):
    seed=Decimal(str(initial_funded_seed))
    if not seed.is_finite() or seed<=0:
        raise ValueError("STAGING_A_INITIAL_FUNDED_SEED_INVALID")
    return seed/BASE_SEED


def normalized_parent_ceiling(initial_funded_seed):
    return BASE_PARENT_CEILING*funded_scale(initial_funded_seed)


def staged_sol_child(admitted_quantity,initial_funded_seed,venue_lot):
    admitted=Decimal(str(admitted_quantity));lot=Decimal(str(venue_lot))
    if not admitted.is_finite() or admitted<0 or not lot.is_finite() or lot<=0:
        raise ValueError("STAGING_A_QUANTITY_OR_LOT_INVALID")
    return (min(admitted,BASE_SOL_CHILD*funded_scale(initial_funded_seed))//lot)*lot
