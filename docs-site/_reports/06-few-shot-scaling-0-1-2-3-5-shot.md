---
title: "Few-shot scaling (0/1/2/3/5-shot)"
nav_order: 6
---

Same task prompts, N correct in-task exemplars prepended before the question. Numbers below are the mean over the 7 tasks; see `persian_nshot.png`.


### Qwen2.5-7B Instruct

| Shots | Mean | Persian ARC (MC) | Parsinlu MC | Persian Math | Sentiment | Entailment | NER | Reading Comp. |
|---|--:|---|---|---|---|---|---|---|
| 0 | 0.443 |0.680 | 0.360 | 0.380 | 0.660 | 0.000 | 0.880 | 0.140 |
| 1 | 0.454 |0.620 | 0.380 | 0.120 | 0.800 | 0.000 | 0.980 | 0.280 |
| 2 | 0.466 |0.740 | 0.320 | 0.120 | 0.780 | 0.000 | 0.960 | 0.340 |
| 3 | 0.503 |0.700 | 0.440 | 0.240 | 0.800 | 0.000 | 0.980 | 0.360 |
| 5 | 0.520 |0.660 | 0.500 | 0.260 | 0.800 | 0.000 | 0.980 | 0.440 |
