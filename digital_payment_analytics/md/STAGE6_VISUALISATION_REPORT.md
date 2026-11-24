# Stage 6 — Visualisation and Communication

**Tooling:** Python 3.13, pandas 3.0, matplotlib 3.10  
**Script:** `stage6_dashboard.py`  
**Outputs:** `stage6_outputs/00_dashboard.png`, `01_…png` … `06_…png`, `chart_index.txt`

---

## 1. Communication design

This stage presents the main findings of Stages 3–5 as a **coherent set of six question-led charts** plus a **compact dashboard**. The following rules were applied to every figure:

* **One question per chart.** No chart exists merely to fill space; each answers a specific analytical question.
* **Clear title.** Titles are phrased as the question being answered (e.g. "Which segments are digital-first?").
* **Labelled axes with units.** Counts are labelled "Number of transactions", monetary values "BND", rates "%". Percentages are also shown in bar labels where useful.
* **Short interpretation on the figure.** Every chart carries a one- or two-sentence interpretation beneath the plot, so it can be understood without reading this report.
* **Honest comparison.** Bars are sorted to support ranking, sample sizes (`n = …`) are shown for category spend, and small-group caveats are stated in the interpretations where relevant.
* **No decorative elements.** No 3-D effects, no unnecessary legends, no dual axes that could mislead, and no charts that repeat the same information in a different shape.

---

## 2. Compact dashboard overview

![Dashboard of six main findings](stage6_outputs/00_dashboard.png)

*Figure 0 — One-page dashboard. Panels Q1–Q6 correspond to the individual charts below; each panel retains its own title, axis labels, units and interpretation.*

The dashboard is designed to be read top-left to bottom-right: it starts with the **channel mix**, moves to **where spend comes from**, then **who uses digital rails**, **whether outcomes differ**, **geography** and finally **extreme values**. This ordering moves from broad structure to specific risk/outlier questions.

---

## 3. Individual charts and interpretations

### Q1 — Which payment channels are used most?

![Channel usage](stage6_outputs/01_channel_usage.png)

**Axes:** x = number of transactions (share shown in brackets); y = payment channel.  
**Interpretation:** Debit Card is the single most used rail (20.1%); wallet + QR together reach 38.0%, so no channel dominates the mix.  
**Why this chart:** A horizontal sorted bar chart makes the near-even channel split immediately visible; a pie chart would obscure the small differences between 20.1%, 19.3% and 18.8%.

---

### Q2 — Which categories generate the most spend?

![Category spend](stage6_outputs/02_category_spend.png)

**Axes:** x = successful transaction value (BND); y = merchant category. Bar labels include transaction count `n`.  
**Interpretation:** Restaurant and Grocery lead by count, but Retail (200.7k BND) and Travel (133.4k BND from only 174 payments) drive value.  
**Why this chart:** Ranking by total value while printing `n` prevents the reader from confusing a high-volume, low-ticket category (Grocery) with a low-volume, high-ticket one (Travel). Only successful payments are included, so the metric is realised spend.

---

### Q3 — Which segments are digital-first?

![Segment digital adoption](stage6_outputs/03_segment_digital.png)

**Axes:** x = wallet + QR share of successful payments (%); y = customer segment.  
**Interpretation:** Tech Savvy customers use wallet/QR for 66.2% of payments versus 13.3% for Senior Citizens — a segment gradient, not an income effect.  
**Why this chart:** A single percentage metric on a common scale allows fair comparison across unequal segment sizes. The colour split at 40% is a visual guide only; the exact values are labelled.

---

### Q4 — Do outcomes differ by payment channel?

![Outcome mix by channel](stage6_outputs/04_channel_outcomes.png)

**Axes:** x = share of channel transactions (%); y = payment channel. Legend = transaction status.  
**Interpretation:** Success stays within 93.2–95.4% across channels; the small spread is consistent with sampling variation, not a channel performance effect.  
**Why this chart:** A 100% stacked bar keeps each channel's row comparable regardless of its volume, which a raw count chart would not. The interpretation explicitly resists a causal reading.

---

### Q5 — Where do payments concentrate?

![Geography](stage6_outputs/05_geography.png)

**Axes:** x = number of transactions (share in brackets); y = district. The inset reports mean value by urbanity in BND.  
**Interpretation:** Brunei-Muara accounts for 68.4% of payments, while mean values by urbanity are similar (160–176 BND): volume is concentrated, amounts are not.  
**Why this chart:** The bar answers the "where" question directly; the inset prevents the reader from incorrectly assuming that the busiest district also has the largest payments.

---

### Q6 — Are there extreme payment values?

![Value outliers](stage6_outputs/06_value_outliers.png)

**Axes:** x = transaction value (BND); y = number of transactions. Dashed lines mark the median and the Tukey upper fence.  
**Interpretation:** 225 payments (4.5%) exceed 491.54 BND and 122 are Travel — an expected tail from wide Travel value ranges, not necessarily data errors.  
**Why this chart:** A histogram with explicit statistical fences communicates skewness and outlier frequency far better than summary statistics alone. The annotation names the dominant category so the reader can judge whether the tail is plausible.

---

## 4. Notes on consistency and limitations

* All figures are derived directly from the Stage 2 CSVs, so they are consistent with the pandas EDA (Stage 3), MongoDB aggregations (Stage 4) and Spark answers (Stage 5).
* The segment–channel gradient, category value ranges and income scaling were programmed into the synthetic generator. The charts **communicate the dataset's structure**; they are not evidence of real-world causal relationships.
* Q4 and Q6 include explicit cautions about small differences and expected tails, avoiding the common visualisation mistake of over-reading noise.

---

## 5. Reproduce

```powershell
cd "C:\Users\ASUS\Documents\Big Data Tech Task"
python digital_payment_analytics\stage6_dashboard.py
```

The script rewrites all seven PNGs and `chart_index.txt` in `stage6_outputs\`.
