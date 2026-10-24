# Root acceptance supplement — same correction batch

Source88a28bc, market_redesign.py `_md_reconcile`: an actual first partial fill can be smaller than3valid TP allocations even when the planned first half passed preflight. The existing branch records PARTIAL_BELOW_THREE_VALID_LOTS and returns. If the first IOC then becomes terminal, waiting for three accepted targets also blocks the second child; the tiny inventory can remain indefinitely without a real protective exit. A reason receipt alone is not the requested temporary protective state.

Required within the already active single correction batch: pending first-child fills may temporarily remain in an explicitly logged protection exception. At terminal first-child outcome with insufficient inventory for three valid TP, stop increases/cancel remaining entry and use the existing native close/market_exit path for the actual inventory, with an explicit insufficient-three-targets reason until nativeflat. No fabricated tiny TP, no arbitrary new BTC price stop and no extra entry. Test actual protective action/ownership/flat state and duration, not only a log message. This is execution admissibility handling, not a new tuned trading hypothesis.

The two independent-reviewP1 findings remain in review-88a28bc.md. This supplement does not authorize another correction cycle or any physical full launch.

Crash/open-position recovery is still UNPROVEN: new research state is in-memory, as the legacy split state. Preserve PROJECT_TRUTH manual reconciliation/failclosed boundaries; do not build a new recovery service in this research checkpoint or imply restart/live acceptance from cache callback tests or JSON roundtrip. Report this missing task qualification explicitly, even if future numerical50/90 checks pass.
