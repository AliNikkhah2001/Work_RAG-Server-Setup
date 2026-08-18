---
title: "Effect of temperature"
nav_order: 7
---

Same prompts re-run at increasing sampling temperature (greedy 0.0 baseline → 0.2 / 0.5 / 0.8 / 1.0). Higher temperature = more diverse (but less reproducible) answers; label/format tasks typically degrade while reasoning tasks can benefit slightly. See `persian_temperature.png`.


### Qwen2.5-7B Instruct

| T | Mean | Persian ARC (MC) | Parsinlu MC | Persian Math | Sentiment | Entailment | NER | Reading Comp. |
|---|--:|---|---|---|---|---|---|---|
| 0 | 0.443 |0.680 | 0.360 | 0.380 | 0.660 | 0.000 | 0.880 | 0.140 |
| 0.2 | 0.346 |0.680 | 0.360 | 0.160 | 0.400 | 0.000 | 0.700 | 0.120 |
| 0.5 | 0.334 |0.700 | 0.360 | 0.180 | 0.400 | 0.000 | 0.580 | 0.120 |
| 0.8 | 0.354 |0.720 | 0.360 | 0.240 | 0.380 | 0.020 | 0.640 | 0.120 |
| 1 | 0.369 |0.700 | 0.360 | 0.180 | 0.460 | 0.000 | 0.760 | 0.120 |
