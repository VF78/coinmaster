# Context and unaveraged numeric controls

Both fixed DEVELOPMENT runs completed once; all8496 outer origins/full expanding prefixes retained. Context:6joint ES/refit fits,36.863s,5201optimizer steps; selected epochs3/8/1. Flat:0encoder fits,32.048s. Both overall gates remain NO_SKILL; CHECK/pilot/native/economics untouched.

Every value below is **candidate minus comparator loss**, so negative is better. CIs use the same paired14d calendar blocks,1000draws/seed7; only29blocks and reused DEVELOPMENT do not guarantee coverage or independent confirmation.

| Candidate / comparator | Head | F1 | F2 | F3 | Overall delta [95%CI] | Candidate fold wins |
|---|---|---:|---:|---:|---|---:|
| Context / original CNN | D |−.006349|+.064920|+.009645|+.023096 [−.005559,+.051819]|1/3|
| Context / original CNN | Qlong |−.000415|+.000011|+.002244|+.000608 [−.002318,+.003590]|1/3|
| Context / original CNN | Qshort |+.003628|+.008112|+.005926|+.005908 [+.000342,+.012215]|0/3|
| Flat / corrected grouped numeric | D |+.011162|+.007446|−.011034|+.002567 [−.007945,+.013159]|1/3|
| Flat / corrected grouped numeric | Qlong |+.000918|+.000756|−.002668|−.000322 [−.002022,+.001275]|1/3|
| Flat / corrected grouped numeric | Qshort |−.000214|+.000137|−.001831|−.000629 [−.003087,+.002042]|2/3|

Original CNN adds short-Q evidence relative to the context-only control: all3folds and the paired CI favor CNN. D and long-Q incremental differences remain unresolved. This does **not** establish CNN skill against the fit prior: original CNN short-Q minus prior is only about−.000122 with CI including0. Removing the window also changes head parameter count/capacity, so the comparison does not identify causal image information independently of capacity/optimization.

Context long-Q minus prior is−.001369 [−.004713,+.002030],2/3folds: weak evidence only. Context D/short-Q and all learned-context kNN heads fail. Its kNN deliberately retained common conservative raw256h support, preventing a shorter169h eligibility advantage.

Removing four-bar averaging preserves temporal positions, but Flat780 dimensions did not resolve an improvement over grouped204 dimensions. Even its2/3short-Q wins versus grouped numeric have a CI crossing0; versus the prior Flat short-Q is worse by+.004733 [+.001359,+.007917]. Higher dimensionality changes geometry despite retaining the same fit-standardization/L2/cosine procedure. No new weight normalization or distance rule was introduced.

All69 saved forecast groups passed canonical ID/truth/schema/hash validation. All60 reused control NPZ files are byte-identical to corrected FORM00. Source and25focused/reused tests, optimizer counts, exact per-fold deltas and local artifact hashes are preserved in the neighboring freeze/QA/CSV/manifest files. The separately authorized spatial pooling experiment changes only the readout/head shape and awaits its own complete result; these negative controls do not authorize any economic promotion.
