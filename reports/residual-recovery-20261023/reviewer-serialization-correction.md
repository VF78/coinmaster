# C1 serialization-only correction review

**GO for the minimal observer serialization correction `78cb85aca1cf5c2e4455f5c5ddf02851cfb40076`, parent `78100d4d69a12144a92dbb9a713b7a7f7ce2f54d`. No economic or order-policy change found. This review does not authorize a historical retry.**

Independently read actual canonical Git delta, final HEAD, clean worktree and the two changed file hashes. Product delta is one witness expression: ATTEMPT_SUBMIT copies the existing confirmation dictionary and represents its `close` as an exact decimal string. The original stored confirmation remains Decimal; numeric trigger/reclaim calculations, target lots, credit, state, native submission, accounting, margin and fees remain unchanged. The production `audit_json_default` serializer is unchanged. There is no float conversion, catch-all fallback or suppression of unknown unsupported objects.

The old78100d4 bounded real-native fixture yielded3native events/17C1events and reproduced `TypeError: Object of type Decimal is not JSON serializable` at `$.c1_audit[10].confirmation.close`, value `Decimal('80')`. This is an actual native-fixture payload. The historical attempt's complete final C1audit was not exported and is unavailable; the fixture is not a reconstruction of that failed attempt.

The new regression serializes the actual native fixture's C1audit, denial counts and terminal-state payload with unchanged `audit_json_default`, parses the JSON back, checks exact decimal value of the copied string and asserts the policy's stored confirmation close remains Decimal. The test runs within the existing long/short actual half-cut/restoration fixture. Archived `owner-serialization-tests.log` reports18PASS/3.51s; owner reports diff-check PASS. Reviewer read test/source delta and receipts without rerunning tests or engines.

Changed hashes: residual_recovery.py `01ea8b85e38cf30c40238130b19c2f90db3e96a983844fe40cf2e8cf587a9776`; test_native_residual_recovery.py `cc624065fe390bf2201a5272424fcab3f5010602591667cfdd9fd384093b30e0`. All other source is unchanged by this correction. Original reviewer-source.md/json remain untouched as pinned by attempt1's protocol.

Attempt1 remains INVALID: engine reached the end but normal final report export failed, exit1, no complete artifact/TOTAL acceptance. Its files are preserved, not manually repaired or rehydrated. Root ledger remains1/4 physical attempts consumed,0active. No retry, repeat, historical result recovery or economic claim is authorized by this report. A fresh corrected-source launch requires root's separate exact GO and consumes another physical slot.

Evidence: owner-serialization-repro.json (explicit fixture provenance); owner-serialization-tests.log; exact canonical78100d4→78cb85a delta; root-launch-budget.json and original C1/completion.json normal_complete=false. This is a narrow serialization review only, not a second source/system audit.
