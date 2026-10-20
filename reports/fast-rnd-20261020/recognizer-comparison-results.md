# Frozen recognizer comparison: NO_INFO_ADVANTAGE

All four recognizers completed on identical **5,959 train and 3,432 validation IDs**. The frozen function returned NO_ADDED_DIAGNOSTIC_INFORMATION: no recognizer beats both controls. No model was selected; no OOF, Optuna or policy fitting was launched.

| Model | BTC log loss | SOL log loss | Mean log loss | BTC Brier | SOL Brier | Fit seconds | Inference seconds |
|---|---:|---:|---:|---:|---:|---:|---:|
| prior | 1.101264 | 1.099908 | 1.100586 | 0.668127 | 0.667769 | 0.000 | 0.000 |
| simple | 1.298052 | 1.427181 | 1.362616 | 0.752564 | 0.840077 | 3.731 | 0.274 |
| stumpy | 1.119859 | 1.127457 | 1.123658 | 0.678988 | 0.684573 | 253.620 | 66.968 |
| minirocket | 7.125161 | 7.300339 | 7.212750 | 1.251131 | 1.229265 | 72.438 | 4.584 |
| rdst | 9.180663 | 7.822217 | 8.501440 | 1.375678 | 1.327055 | 208.741 | 16.477 |
| cnn | 1.265970 | 1.272219 | 1.269094 | 0.750632 | 0.760472 | 3459.731 | 94.520 |

The prior has the lowest validation loss. STUMPY and CNN beat the weak simple logistic control but do not beat the prior. MiniRocket and RDST score substantially worse. This is a valid negative for the fixed recipes, not an economic counterfactual.

All probability, ID and input-hash checks passed. Each output is 3,432×2×3, finite, nonnegative and normalized within 1e-6. Saved log loss and Brier scores reproduced within 1e-10. The combined CNN NPY and CSV probabilities agree exactly.

Each model has 48 greedy 72-hour-spaced validation episodes. Spacing is not a significance test. Companion files contain class frequencies, calibration, monthly log loss and Brier scores. Multiclass Brier is the sum across three classes.

The frozen rule requires an improvement over both controls and BTC performance no worse than the simple control. Relative mean-loss differences below 1% favor lower measured cost and then the simpler recipe. No recognizer qualified, so the tie rule was unused.

Only past T metadata and required V labels through 2026-04-04T23:00:00+00:00 were processed; zero U records were processed. CNN averages seeds 7 and 42; both chose 3 inner-T epochs and refit 3, with the authorized batch 32 memory exception. No individual seed was selected.

Costs are successful reported stage costs; earlier OOM attempts, probes, environment and data preparation are excluded. V was already researched and is not fresh independent evidence. These diagnostic results do not establish trading ROI or drawdown.

Source: c1d0c69; numeric source SHA c9312d7e…; dataset manifest 8f51abe5…. U remains closed.
