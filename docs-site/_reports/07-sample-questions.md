---
title: "Sample questions — one tricky prompt per category"
nav_order: 7
---

### 4c. Sample questions — one tricky prompt per category, all models

For each of the 7 task categories below, a deliberately *tricky* prompt is shown where the 9 models **disagree** (best view of real capability). Every model received the exact same input (same dataset row, same index); outputs are raw, including `thinking` blocks where models emit them. Qwen2.5-7B appears twice: **0-shot** and **2-shot** (`--n-shots 2`). Scores are the model's overall Persian-eval mean (0–1); `✓/✗` is whether it got this specific question right.

#### ARC — elementary science (multiple choice)

**Input:**

```
سؤال: یک دانش‌آموز به‌تازگی فعالیت آزمایشگاهی را به پایان رسانده است. آخرین اقدامی که دانش‌آموز باید قبل از ترک محل آزمایشگاه انجام دهد چیست؟
گزینه‌ها:
A)  شستن دست‌ها
B)  خاموش کردن همه تجهیزات
C)  جمع‌آوری کلیه ظروف شیشه‌ای
D)  شستن وسایل و میزهای آزمایش
فقط حرف گزینه درست را بگو:
```

**Gold:** `a`


| Model | Overall mean | This question | Output (abridged) |
|---|---|---|---|
| **Gemma-4-31B** | 0.663 | ✅ | `A` |
| **Gemma-3-27B** | 0.600 | ✅ | `A` |
| **Nemotron-49B** | 0.494 | ❌ | `B` |
| **Qwen3.8-27B** | 0.477 | ✅ | `A` |
| **Qwen2.5-7B (2-shot)** | 0.466 | ❌ | `b c` |
| **Qwen2.5-7B** | 0.443 | ❌ | `B) خاموش کردن همه تجهیزات` |
| **Llama-3.2-3B** | 0.326 | ✅ | `A` |
| **Qwen3-30B-A3B** | 0.283 | ❌ | `B` |
| **Mistral-7B** | 0.186 | ✅ | `A) شستن دست‌ها` |
| **Phi-3-mini** | 0.143 | ❌ | `D) شستن وسایل و میزهای آزمایش در این اقدامی، دانش‌آموز می‌کنند وسایل و میزهای آزمایش را می‌شوند و از آن‌ها تج…` |

**Why it's tricky:** All 9 models saw the same lab-safety question; the correct answer is **A**. Gemma-4, Gemma-3, Qwen3.8 and Llama-3.2 comply with the 'answer one letter' instruction, but Nemotron-49B, Qwen2.5-7B, Qwen3-30B and Phi-3-mini choose an *arguably reasonable* but wrong option — showing that ARC scores separate models on Persian science reasoning, not just on format-following.

#### Parsinlu multiple choice (analogy/grammar)

**Input:**

```
در ادامه، به شما یک سوال چند گزینه‌ای به زبان فارسی نشان داده می شود. شما باید بر اساس دانش خود به سوال پاسخ دهید. پاسخ خود را از بین گزینه‌های داده شده انتخاب کنید.
فقط عدد متناظر با گزینه درست را خروجی بده.
سوال: '''۸ نفر کارگر، کاری را در مدت ۲۰ روز تمام می‌کنند دو نفر کارگر به این عده افزوده می‌شود: این کار چند
روز زودتر به پایان می‌رسد؟
'''
گزینه ها: '''1. ۱۶ روز
2. ۴ روز
3. ۵ روز
4. ۲ روز''
```

**Gold:** `جواب: گزینه 2`


| Model | Overall mean | This question | Output (abridged) |
|---|---|---|---|
| **Gemma-4-31B** | 0.663 | ✅ | `2` |
| **Gemma-3-27B** | 0.600 | ✅ | `2` |
| **Nemotron-49B** | 0.494 | ❌ | `4` |
| **Qwen3.8-27B** | 0.477 | ✅ | `2` |
| **Qwen2.5-7B (2-shot)** | 0.466 | ✅ | `گزینه 2` |
| **Qwen2.5-7B** | 0.443 | ❌ | `3` |
| **Llama-3.2-3B** | 0.326 | ✅ | `گزینه ۲` |
| **Qwen3-30B-A3B** | 0.283 | ❌ | `<think> Okay, let's try to figure out this problem. So, the question is about workers completing a job and ho…` |
| **Mistral-7B** | 0.186 | ❌ | `1. 16 روز` |
| **Phi-3-mini** | 0.143 | ❌ | `این کار ۱۶ روز به پایان می‌رسد. این کار ۴ روز به پایان می‌رسد. این کار ۵ روز به پایان می‌رسد. این کار ۲ روز ب…` |

**Why it's tricky:** A workers/rate word problem: 8 workers finish in 20 days; adding 2 workers finishes it how many days *earlier*? (gold `2` = ۴ روز). Gemma-4, Gemma-3, Qwen3.8, Qwen2.5-7B (2-shot) and Llama-3.2 answer the option number correctly; Nemotron and Qwen2.5-7B (0-shot) pick wrong options (`4`/`3`), Mistral answers `1. 16 روز`, Phi-3-mini prints *every* option, and Qwen3-30B wraps its answer in a `thinking` block (truncated). Format-following (bare option number) decides the winner.

#### Persian math word problem

**Input:**

```
به عنوان یک متخصص ریاضی، یک مسئله به شما داده خواهد شد و باید راه حل صحیح، شفاف و قدم به قدم برای مسئله نوشته و پاسخ نهایی به تنهایی را در بخش مربوطه قرار دهید. تمامی پاسخ های شما باید به زبان فارسی باشد بجز اعداد که به لاتین (انگلیسی) باید نوشته بشوند. از شما انتظار میرود مسئله را در فرمت زیر دریافت کرده و بصورت مشخص شده، راه حل و پاسخ نهایی را ارائه کنید:

[مسئله]
در این بخش، صورت مسئله به شما د
```

**Gold:** `1000`


| Model | Overall mean | This question | Output (abridged) |
|---|---|---|---|
| **Gemma-4-31B** | 0.663 | ✅ | `[راه حل] ابتدا مقدار پنج درصد از 2000 را محاسبه می‌کنیم: 5% * 2000 = (5/100) * 2000 = 5 * 20 = 100 سپس طبق صو…` |
| **Gemma-3-27B** | 0.600 | ✅ | `[راه حل] پنج درصد از 2000 برابر است با: (5/100) * 2000 = 100 فرض می‌کنیم عدد مورد نظر x باشد. ده درصد از x بر…` |
| **Nemotron-49B** | 0.494 | ✅ | `[راه حل] پنج درصد از 2000 را محاسبه می کنیم: 5% از 2000 = 0.05 * 2000 = 100 اکنون، ما می خواهیم بدانیم 100 مع…` |
| **Qwen3.8-27B** | 0.477 | ✅ | `[راه حل] پنج درصد از 2000 برابر است با: 0.05 × 2000 = 100 اگر عدد مورد نظر را x فرض کنیم، ده درصد از آن برابر…` |
| **Qwen2.5-7B (2-shot)** | 0.466 | ❌ | `[راه حل] ابتدا می‌توانیم معادله را برای این مسئله بنویسیم. فرض کنیم x عدد مورد نظر ما است. پنج درصد از 2000 ب…` |
| **Qwen2.5-7B** | 0.443 | ✅ | `[راه حل] ابتدا می‌توانیم معادله را برای حل این مسئله بنویسیم. فرض کنیم x عدد مورد نظر ما است. پنج درصد از 200…` |
| **Llama-3.2-3B** | 0.326 | ❌ | `[مسئله] پنج درصد از 2000 معادل ده درصد از چه عددی است؟ [/مسئله] [راه حل] پنج درصد از 2000 را می توان به صورت …` |
| **Qwen3-30B-A3B** | 0.283 | ❌ | `<think> Okay, let's see. The problem is asking: 5% of 2000 is equal to 10% of what number? Hmm, I need to fin…` |
| **Mistral-7B** | 0.186 | ❌ | `[راه حل] ابتدا باید پنج درصد از 2000 را حساب کنیم: 2000 * 5/100 = 100. سپس باید ده درصد از چه عددی است: 100 *…` |
| **Phi-3-mini** | 0.143 | ❌ | `کم کوی انجادی اسئده افراری انجادید است اسئ است اسئده ادی است اسئدادید اندادیده اسئده اسئداد ادیدادید ادیدمادی…` |

**Why it's tricky:** '5% of 2000 is equal to 10% of what number?' (gold `1000`). Five models — Gemma-4, Gemma-3, Nemotron, Qwen3.8 and Qwen2.5-7B (0-shot) — work it correctly; Qwen2.5-7B **2-shot misses** (the exemplar anchors a different structure), Llama-3.2 and Mistral set up the equation but never output the final-answer block, and Phi-3-mini degrades into gibberish. Math scores are gated by final-answer *structure compliance*, and few-shot can actually hurt.

#### Sentiment analysis

**Input:**

```
جمله زیر نظر یک شخص است. این جمله به زبان فارسی است. بار یا احساس موجود در این جمله را شناسایی کن.
پاسخ‌ های ممکن کلمات روبرو هستند: POSITIVE, NEUTRAL, NEGATIVE, OTHER.
زمانی که جمله دارای احساس خاصی نیست یا شامل احساسات مختلف است از OTHER استفاده کن
نظر: اگه نوشیدنی مالته باید تلخ باشه نه اینکه شیرین از خریدم کاملا پشیمونم و ب هیچ کسم پیشنهاد نمیکنم ک بخره چون پشیمون میشید تو عمرم با همچین نوشیدن
```

**Gold:** `احساس: NEGATIVE`


| Model | Overall mean | This question | Output (abridged) |
|---|---|---|---|
| **Gemma-4-31B** | 0.663 | ✅ | `NEGATIVE` |
| **Gemma-3-27B** | 0.600 | ✅ | `NEGATIVE **توضیح:** این جمله به وضوح بیانگر نارضایتی شدید و پشیمانی از خرید نوشیدنی است. کلماتی مانند "پشیمون…` |
| **Nemotron-49B** | 0.494 | ❌ | `با توجه به تحلیل احساسات در جمله ارائه شده، بار یا احساس موجود در این جمله را می‌توان به شرح زیر شناسایی کرد:…` |
| **Qwen3.8-27B** | 0.477 | ✅ | `NEGATIVE` |
| **Qwen2.5-7B (2-shot)** | 0.466 | ✅ | `احساس: NEGATIVE` |
| **Qwen2.5-7B** | 0.443 | ❌ | `برای شناسایی بار یا احساس موجود در این جمله، باید به محتوای آن نگاه کنیم: "زمانی که جمله دارای احساس خاصی نیس…` |
| **Llama-3.2-3B** | 0.326 | ✅ | `در این جمله احساس منفی وجود دارد.` |
| **Qwen3-30B-A3B** | 0.283 | ❌ | `**بار/احساس:** NEGATIVE **توضیح:** جمله شامل عباراتی مانند "پشیمونم"، "ب هیچ کسم پیشنهاد نمیکنم"، و "پشیمون م…` |
| **Mistral-7B** | 0.186 | ❌ | `NEUTRAL` |
| **Phi-3-mini** | 0.143 | ❌ | `این جمله بررو نیز نگرفته است که احساسات مختلف دارد. این می‌تواند نوشیدنی مالته باید تلخ باشند و نیاز بود به ش…` |

**Why it's tricky:** A product review — 'نوشیدنی مالته باید تلخ باشه نه شیرین… کاملا پشیمونم' — is clearly **NEGATIVE**. Gemma-4, Gemma-3, Qwen3.8, Llama-3.2 and Qwen2.5-7B (2-shot) get it; Mistral-7B says `NEUTRAL`, Qwen2.5-7B and Nemotron hedge with long explanations the scorer can't map, and Qwen3-30B emits the right label *after* a `thinking` block (truncation cost). A free-form task where prose length and label discipline matter as much as comprehension.

#### Natural language entailment

**Input:**

```
هدف وظیفه‌ی استنتاج زبان طبیعی تشخیص رابطه‌ی نتیجه‌گیری بین یک <فرضیه> با توجه به یک <پیش‌فرض> است.
رابطه‌ یا برچسب میان آن‌ها می‌تواند یکی از سه نوع تناظر، تناقض یا ناشناخته باشد.
- تناظر : اگر جمله <فرضیه> به طور منطقی نتیجه‌ای از جمله <پیش‌فرض> باشد
- تناقض : اگر جمله <فرضیه> با جمله <پیش‌فرض> در تناقض باشد
- ناشناخته : اگر رابطه‌ای قطعی بین جمله <پیش‌فرض> و جمله <فرضیه> وجود نداشته باشد و هیچ 
```

**Gold:** `<برچسب>: c`


| Model | Overall mean | This question | Output (abridged) |
|---|---|---|---|
| **Gemma-4-31B** | 0.663 | ❌ | `ناشناخته` |
| **Gemma-3-27B** | 0.600 | ✅ | `تناقض` |
| **Nemotron-49B** | 0.494 | ✅ | `تناقض` |
| **Qwen3.8-27B** | 0.477 | ❌ | `We need answer in Persian likely. User asks NLI: premise: "رسوب اسیدی یا باران اسیدی وقتی که SO2 و NOx در اتم…` |
| **Qwen2.5-7B (2-shot)** | 0.466 | ❌ | `ناشناخته` |
| **Qwen2.5-7B** | 0.443 | ❌ | `تناظر` |
| **Llama-3.2-3B** | 0.326 | ✅ | `تناقض` |
| **Qwen3-30B-A3B** | 0.283 | ✅ | `<think> Okay, let's try to figure out the relationship between the given premise and hypothesis. The premise …` |
| **Mistral-7B** | 0.186 | ❌ | `تناظر` |
| **Phi-3-mini** | 0.143 | ✅ | `<برچسب>: تناقض یا تناظر یا ناشناخته می تواند این رابطه برای توجه به توانایی استفاده کند که این اتمسفر با اکسی…` |

**Why it's tricky:** The gold label is `<برچسب>: c` (تناقض/contradiction) — acid-rain premise vs hypothesis. **Half the models miss even this** (the task's best model only scores 0.26). Gemma-3, Nemotron, Llama-3.2 and Phi-3 pick تناقض (Qwen3-30B also hits, label hidden inside a `thinking` block); Gemma-4 and Qwen2.5 say ناشناخته, Mistral/Qwen2.5 say تناظر, Qwen3.8 answers in an English preamble. The *right-class* accuracy would be much higher — most failures are output-format, but the underlying NLI signal is genuinely the hardest of the seven tasks.

#### Named entity recognition (Persian tokens)

**Input:**

```
شرح وظیفه:
شما باید یک لیست توکن فارسی داده شده را با برچسب های موجودیت اسمی برچسب گذاری کنید.
برچسب های موجودیت اسمی:

PER (نفر)
LOC (مکان)
ORG (سازمان)
Product (محصول)
Event (رویداد)
Facility (تاسیسات)

فرمت خروجی:
فرمت خروجی شما باید لیستی از تاپل ها باشد، که در آن هر تاپل از یک کلمه از متن ورودی و برچسب موجودیت اسمی مربوط به آن تشکیل شده باشد.
برای کلماتی که بخشی از هیچ موجودیت اسمی نیستند، با
```

**Gold:** `خروجی  [('وی', 'o'), ('درباره', 'o'), ('مراحل', 'o'), ('احداث', 'o'), ('بزرگراه', 'facility'), ('نیاوران', 'facility'), ('گفت', 'o'), (' ', 'o'), ('با', 'o'), ('توجه', 'o'), ('به', 'o'), ('توافق', 'o'`


| Model | Overall mean | This question | Output (abridged) |
|---|---|---|---|
| **Gemma-4-31B** | 0.663 | ✅ | ````python [ ('وي', 'O'), ('درباره', 'O'), ('مراحل', 'O'), ('احداث', 'O'), ('بزرگراه', 'FAC'), ('نیاوران', 'LO…` |
| **Gemma-3-27B** | 0.600 | ✅ | ```` [('وي', 'PER'), ('درباره', 'O'), ('مراحل', 'O'), ('احداث', 'O'), ('بزرگراه', 'Facility'), ('نیاوران', 'LO…` |
| **Nemotron-49B** | 0.494 | ✅ | `زیرا در متن ورودی داده شده، هیچ نام خاص برای افراد (PER)، سازمان (ORG)، محصول (Product)، رویداد (Event) یا تا…` |
| **Qwen3.8-27B** | 0.477 | ❌ | `We need answer in Persian likely. User asks NER labeling for Persian token list. Need output list of tuples (…` |
| **Qwen2.5-7B (2-shot)** | 0.466 | ✅ | `خروجی برای ورودی شما به صورت زیر خواهد بود: [('وي', 'per'), ('درباره', 'o'), ('مراحل', 'o'), ('احداث', 'o'), …` |
| **Qwen2.5-7B** | 0.443 | ✅ | `برای برچسب‌گذاری لیست توکن‌های فارسی داده شده با برچسب‌های موجودیت اسمی، می‌توانیم به شرح زیر عمل کنیم: ```pl…` |
| **Llama-3.2-3B** | 0.326 | ❌ | `این وظیفه شامل việc برچسب گذاری لیست توکن فارسی داده شده با برچسب های موجودیت اسمی است. لیست توکن ورودی است: …` |
| **Qwen3-30B-A3B** | 0.283 | ❌ | `<think> Okay, I need to label the given Persian tokens with the appropriate named entity tags. Let me start b…` |
| **Mistral-7B** | 0.186 | ❌ | `برای گذاری برچسب های موجودیت اسمی برای لیست توکن فارسی در این صورت است: 1. برای کلمات شخصی (PER): کلماتی که ن…` |
| **Phi-3-mini** | 0.143 | ❌ | `در استفاده از موجودیت اسمی که برچسب می‌کنند، می‌توانید یک لیست توکن فارسی با تاپ‌های موجودیت اسمی برای این مو…` |

**Why it's tricky:** The input list has facility/location tokens (بزرگراه نیاوران …). Gemma-4/Gemma-3 and Qwen2.5-7B emit the expected `[('tok','LABEL'), …]` tuples (hit); Qwen3-30B and Qwen3.8 get stuck in `thinking`/English preamble; Llama-3.2, Mistral, Phi-3 reply with instructions *instead of* the labeled list. **Qwen2.5-7B 2-shot jumps from prose to clean tuples** — few-shot examples fix NER format-following better than a bigger model.

#### Reading comprehension

**Input:**

```
متن: از آنجا که قطر رئوس غیر مجاور را متصل می‌کند، یک مثلث نمی‌تواند قطر داشته باشد و یک چهارضلعی (مربع یا مستطیل) دو قطر دارد. تمام قطرهای یک چندضلعی کوژ درون آن هستند، اما چند قطر یک چندضلعی کاو بیرون از آن قرار می‌گیرد.

سؤال: کدام شکل هندسی قطر ندارد؟
پاسخ:
```

**Gold:** `مثلث`


| Model | Overall mean | This question | Output (abridged) |
|---|---|---|---|
| **Gemma-4-31B** | 0.663 | ✅ | `مثلث` |
| **Gemma-3-27B** | 0.600 | ✅ | `مثلث.` |
| **Nemotron-49B** | 0.494 | ✅ | `پاسخ: مثلث` |
| **Qwen3.8-27B** | 0.477 | ✅ | `مثلث` |
| **Qwen2.5-7B (2-shot)** | 0.466 | ❌ | `مثلث کدام شکل هندسی‌ای است که قطر ندارد.` |
| **Qwen2.5-7B** | 0.443 | ❌ | `برای پاسخ به این سوال، باید به متن دقت کرد و اطلاعات آن را تحلیل کنیم. متن اشاره کرده است که: 1. مثلث قطر ندا…` |
| **Llama-3.2-3B** | 0.326 | ✅ | `مثلث` |
| **Qwen3-30B-A3B** | 0.283 | ❌ | `پاسخ: مثلث توضیح: قطر یک چندضلعی خطی است که دو رأس غیر مجاور را به هم متصل می‌کند. در یک مثلث (سه ضلعی)، تمام…` |
| **Mistral-7B** | 0.186 | ❌ | `یک مثلث قطر ندارد.` |
| **Phi-3-mini** | 0.143 | ❌ | `قطر هندسی ندارد، اما این موضوع به مورد مثلث هندسی است که برای قطر می‌تواند استفاده کرد. مثلث هندسی یک مثلث می…` |

**Why it's tricky:** The passage says a triangle cannot have a diagonal → answer **مثلث**. Top models, Llama-3.2 and Qwen3.8 answer in one word; Mistral, Phi-3, Qwen3-30B and Qwen2.5-7B either paraphrase, reproduce the passage, or add an explanation that fails the exact-match scorer. RC rewards *extractive brevity* — models that restate the answer as-is win.

