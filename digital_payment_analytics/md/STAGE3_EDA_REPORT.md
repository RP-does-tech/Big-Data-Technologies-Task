# Stage 3 — Exploratory Data Analysis with Python

**Dataset:** Brunei Digital Payment Analytics (Stage 2 synthetic CSVs)  
**Tools:** Python 3.13, pandas 3.0, matplotlib 3.10, seaborn 0.13, numpy 2.4 (seaborn is used for the statistical plots; descriptive statistics remain in pandas)  
**Script:** `eda_analysis.py`  
**Outputs:** `eda_outputs/summary_statistics.txt`, 12 PNG figures, `eda_outputs/figure_index.txt`

---

## 1. Objective and approach

This stage describes the data, explores single variables, compares pairs of variables and looks at a few multivariate views. The aim is to identify **patterns, differences, relationships and possible anomalies**. All statements below are descriptive or associational. **No correlation is interpreted as proof of causation** — see §8.

---

## 2. Data preparation

The 5,000-row transaction fact table was enriched with:

* customer attributes from `data/customers.csv` (age, gender, occupation, income band, preferred channel, self-reported frequency),
* location attributes from `data/locations.csv` (district, urbanity, latitude, longitude).

Resulting analysis frame: **5,000 rows × 30 columns**, covering **2025-01-01 to 2025-12-31**.

* **Missing values:** 0 in every column of the merged frame.
* **Derived fields:** `month`, `month_name` and a numeric `cross_border_flag` were added for plotting/correlation only.
* **Consistency checks inherited from Stage 2:** 0 foreign-key violations, 0 denormalisation mismatches, 0 date/hour derivation errors.

---

## 3. Descriptive statistics

### 3.1 Numeric variables (transaction-weighted)

| Variable | Count | Mean | Std | Min | 25% | Median | 75% | Max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `transaction_value_bnd` | 5,000 | 162.40 | 195.37 | 2.10 | 40.22 | 93.11 | 220.75 | 1,685.04 |
| `transaction_hour` | 5,000 | 14.66 | 4.37 | 7 | 11 | 15 | 18 | 22 |
| `adoption_tenure_months` | 5,000 | 24.21 | 14.94 | 1 | 11 | 22 | 35 | 60 |
| `age` | 5,000 | 42.31 | 15.58 | 18 | 28 | 39 | 53 | 80 |
| `monthly_income_bnd` | 5,000 | 2,943.50 | 1,716.46 | 500 | 1,500 | 2,500 | 4,000 | 6,000 |

The transaction value distribution is strongly right-skewed: the mean (162.40) is almost 1.75× the median (93.11), and the maximum is more than 7× the 75th percentile.

### 3.2 Categorical snapshot

| Variable | Leading categories (share of 5,000) |
|---|---|
| `payment_channel` | Debit Card 20.1%, Mobile Wallet 19.3%, QR Payment 18.8%, Credit Card 15.2%, Bank Transfer 14.5%, Online Banking 12.2% |
| `merchant_category` | Restaurant 19.0%, Grocery 18.0%, Retail 16.3%, Transportation 12.5%, … Travel 3.5% |
| `transaction_status` | Successful 93.96%, Failed 4.12%, Pending 1.92% |
| `device_type` | Smartphone 60.3%, Computer 22.7%, POS Terminal 17.0% |
| `customer_segment` | Young Professionals 29.2%, Working Adults 22.8%, Tech Savvy 18.4%, Traditional Users 17.8%, Senior Citizens 11.7% |
| `adoption_level` | High 47.6%, Low 29.6%, Medium 22.8% |
| `is_cross_border` | No 94.7%, Yes 5.3% |
| `district` | Brunei-Muara 68.4%, Belait 16.8%, Tutong 9.5%, Temburong 5.3% |
| `urbanity` | Urban 82.9%, Suburban 10.1%, Rural 7.0% |

Full frequency tables, grouped value summaries, cross-tabs and the correlation matrix are in `eda_outputs/summary_statistics.txt`.

---

## 4. Univariate exploration

### 4.1 Transaction value

![Distribution and boxplot of transaction value](eda_outputs/01_value_distribution.png)

*Figure 1 — Histogram and boxplot of `transaction_value_bnd`.*

The histogram/boxplot confirm a long right tail. Most payments are small-to-mid sized, with a sparse tail of large values. The Tukey upper fence is **491.54 BND**; **225 transactions (4.50%)** exceed it. These are examined in §7.

### 4.2 Categorical profile

![Categorical frequency bars](eda_outputs/02_categorical_counts.png)

*Figure 2 — Counts by channel, category, status, device, segment and adoption level.*

No single channel dominates (largest share 20.1%). Smartphones account for 60.3% of payments, consistent with the channel rules. The outcome mix is heavily successful, and cross-border payments are rare.

### 4.3 When payments occur

![Hour, weekday and monthly patterns](eda_outputs/03_temporal_patterns.png)

*Figure 3 — Transactions by hour, day of week and calendar month.*

* Hours run from **07:00 to 22:00 only**; the busiest hours are in the afternoon/evening (mean hour 14.66, median 15). The absence of overnight activity is a generator rule, not a discovered behavioural fact.
* Day-of-week counts are nearly flat (662 Saturday to 741 Sunday, a 12% spread).
* Monthly counts range from **379 to 442**, again close to uniform across 2025.

### 4.4 Customer profile attached to each payment

![Customer attribute distributions](eda_outputs/04_customer_profile.png)

*Figure 4 — Age, income band, adoption tenure and self-reported frequency.*

Age and tenure are broad but shaped by segment rules (e.g. younger Tech Savvy, older Senior Citizens). Income bands are discrete (500–6,000 BND in nine steps). Self-reported frequency is close to evenly split across Daily/Weekly/Occasional/Monthly — in Stage 2 this field was assigned independently of the observed transaction count, so it should not be treated as a behavioural driver here.

---

## 5. Bivariate exploration

### 5.1 Merchant category vs value

![Value by merchant category](eda_outputs/05_value_by_category.png)

*Figure 5 — Boxplots of transaction value by category, sorted by median.*

This is the strongest value difference in the data:

| Category | Count | Mean | Median | Max |
|---|---:|---:|---:|---:|
| Travel | 174 | 796.52 | 810.12 | 1,685.04 |
| Utilities | 420 | 270.23 | 263.38 | 616.09 |
| Retail | 816 | 262.33 | 259.89 | 629.53 |
| Education | 225 | 248.64 | 240.48 | 599.35 |
| Grocery | 899 | 80.01 | 81.15 | 190.76 |
| Restaurant | 949 | 53.73 | 51.85 | 126.32 |
| Transportation | 625 | 27.05 | 26.18 | 63.23 |

Travel median is roughly **31×** Transportation median. This separation is built into the Stage 2 category value ranges, so it is a designed association rather than an emergent market finding.

### 5.2 Customer segment vs payment channel

![Segment by channel heatmap](eda_outputs/06_segment_channel_heatmap.png)

*Figure 6 — Transaction counts by customer segment and payment channel.*

| Segment | Mobile Wallet | QR | Debit | Credit | Online Banking | Bank Transfer |
|---|---:|---:|---:|---:|---:|---:|
| Tech Savvy | 36.1% | 30.4% | 10.4% | 5.4% | 12.4% | 5.2% |
| Young Professionals | 23.1% | 24.2% | 16.2% | 12.7% | 16.2% | 7.7% |
| Working Adults | 15.1% | 18.0% | 21.2% | 15.6% | 13.3% | 16.8% |
| Traditional Users | 8.9% | 7.4% | 29.1% | 24.0% | 7.9% | 22.8% |
| Senior Citizens | 7.2% | 5.8% | 29.3% | 23.0% | 6.1% | 28.6% |

A clear gradient: younger/digitally-oriented segments concentrate in wallet and QR, while Traditional Users and Senior Citizens concentrate in cards and bank transfer. Again, this mirrors the segment-specific channel weights used by the generator.

### 5.3 Adoption, tenure and value

![Adoption and tenure versus value](eda_outputs/07_adoption_tenure_value.png)

*Figure 7 — Value by adoption level and tenure vs value coloured by adoption.*

* Median value by adoption: Low 91.90, Medium 92.52, High 94.07 BND — only a ~2.4% spread.
* Tenure vs value correlation is **r = 0.016** (negligible linear association).
* Age vs tenure is **r = −0.371**, the strongest linear association in the dataset. It is structural: the segment definitions tie younger ages to High adoption and longer allowed tenure, and older ages to Low adoption with a shorter cap.

### 5.4 Channel vs transaction outcome

![Outcome mix by channel](eda_outputs/08_status_by_channel.png)

*Figure 8 — Stacked share of Successful / Failed / Pending by channel.*

Success rates are similar across rails: **93.18% (Credit Card) to 95.44% (Bank Transfer)**, a range of only 2.26 percentage points. Failure rates range 3.04–4.68%. There is no strong channel–outcome association in this synthetic sample; with 608–1,005 transactions per channel and only 206 failures overall, small differences are compatible with sampling variation.

### 5.5 Income band vs value

![Income versus transaction value](eda_outputs/09_income_vs_value.png)

*Figure 9 — Jittered income band against transaction value, coloured by adoption.*

* Pearson **r = 0.107**, Spearman **ρ = 0.109** — a weak positive monotonic association.
* The generator scaled every amount by `0.8 + (income / 2500) × 0.2`, so a small positive association is expected by construction. It is not evidence that income "causes" payment value in a real population.

### 5.6 Geography

![District counts and urbanity means](eda_outputs/10_geography.png)

*Figure 10 — Transaction counts by district and mean value by urbanity.*

* Brunei-Muara contributes **68.4%** of transactions, reflecting the 60% district sampling weight plus its wholly-urban classification and the extra urban sampling boost.
* Mean value by district: Belait 180.03, Tutong 168.20, Brunei-Muara 157.82, Temburong 155.31 BND.
* Mean value by urbanity: Suburban 176.10, Rural 167.29, Urban 160.32 BND. Differences are modest and should be read cautiously because rural/suburban groups are small (352 and 504 rows).

---

## 6. Multivariate exploration

### 6.1 Numeric correlation matrix

![Correlation heatmap](eda_outputs/11_correlation_heatmap.png)

*Figure 11 — Pearson correlations among eight numeric variables.*

| Pair | r | Comment |
|---|---:|---|
| Age ↔ adoption tenure | **−0.371** | Strongest; imposed by segment rules |
| Latitude ↔ longitude | −0.111 | Artefact of uniform sampling in a rectangular bounding box |
| Income ↔ value | 0.107 | Expected from generator scaling |
| Tenure ↔ value | 0.016 | Near zero |
| Value ↔ hour | −0.004 | Near zero |
| Value ↔ cross-border flag | 0.010 | Near zero |

No other pair exceeds |r| = 0.05. The correlation matrix therefore shows a sparse, mostly weak linear structure. Note that Pearson r only captures linear association; categorical relationships (e.g. segment ↔ channel) are much stronger than anything visible here and were examined via cross-tabs instead.

### 6.2 Segment × channel × value, and large payments

![Segment-channel mean value and top payments](eda_outputs/12_multivariate_and_outliers.png)

*Figure 12 — Left: mean value by segment and channel. Right: ten largest individual payments.*

Mean value by segment × channel (BND):

| Segment | Wallet | QR | Debit | Credit | Online Banking | Transfer |
|---|---:|---:|---:|---:|---:|---:|
| Tech Savvy | 180.2 | 158.0 | 147.0 | 149.0 | 188.4 | 121.9 |
| Young Professionals | 164.7 | 162.4 | 193.1 | 136.3 | 160.7 | 155.3 |
| Working Adults | 155.1 | 155.5 | 153.0 | 153.6 | 182.4 | 150.3 |
| Traditional Users | 166.3 | 192.2 | 161.3 | 161.4 | 182.4 | 167.8 |
| Senior Citizens | 156.2 | **209.2** | 156.6 | 174.3 | 134.5 | 132.9 |

The cell means range from 121.9 to 209.2 BND, but group sizes vary widely (e.g. only ~34 Senior-Citizen QR payments), so several extremes are likely small-sample noise rather than stable differences. The right-hand panel shows the ten largest payments; **all ten are Travel**, and all ten come from customers with income bands of 3,000–6,000 BND.

---

## 7. Possible anomalies and data-quality observations

1. **High-value statistical outliers:** 225 transactions (4.50%) lie above the Tukey upper fence of 491.54 BND. By category: Travel 122, Retail 57, Utilities 28, Education 13, Online Shopping 5. The largest is **T004492 at 1,685.04 BND (Travel, Credit Card, income band 6,000)**. These are consistent with the generator's wide Travel range (50–1,500) plus income scaling and rounding — they are extreme but not impossible, so they should be flagged for review rather than deleted.
2. **Right-skewed amount distribution:** mean ≫ median; any modelling that assumes normality (e.g. simple mean±SD thresholds) would misclassify many ordinary Retail/Utilities payments as outliers. Median/IQR or log-based treatment is more appropriate.
3. **Structural zeros / restricted ranges:** no transactions before 07:00 or after 22:00, no missing values, and exactly two currency values (only `BND`). These reflect Stage 2 design choices, not anomalies in the usual data-quality sense.
4. **Uniformity artefacts:** weekday and monthly counts are almost flat, and coordinates are uniformly scattered in a box (producing the mild lat–long correlation). These are synthetic-data fingerprints.
5. **Imposed correlations:** the age–tenure relationship (−0.371) and income–value relationship (0.107) come directly from the generation rules. If a downstream model "discovers" them, it is rediscovering its own input assumptions.
6. **No duplicates or referential problems:** IDs are unique, all foreign keys resolve, and derived date/hour fields match their source timestamp (verified in Stage 2 and again in the EDA load).

---

## 8. Causality statement

Everything reported here is **association or difference observed in a synthetic sample**. Several relationships (segment → channel, category → amount, income → amount, age → tenure) were explicitly programmed into the generator, so observing them is expected and does **not** demonstrate that one variable causes another. Conversely, near-zero correlations do not prove the absence of a relationship — they only indicate no *linear* signal in this sample. No causal claim is made anywhere in this report.

---

## 9. Reproduction and output inventory

```powershell
cd "C:\Users\ASUS\Documents\Big Data Tech Task"
python digital_payment_analytics\eda_analysis.py
```

Generated in `digital_payment_analytics\eda_outputs\`:

| File | Contents |
|---|---|
| `summary_statistics.txt` | Full descriptive statistics, frequency tables, cross-tabs, correlations, outlier counts |
| `01_value_distribution.png` | Value histogram + boxplot |
| `02_categorical_counts.png` | Six categorical frequency charts |
| `03_temporal_patterns.png` | Hour, weekday, month |
| `04_customer_profile.png` | Age, income, tenure, frequency |
| `05_value_by_category.png` | Value by merchant category |
| `06_segment_channel_heatmap.png` | Segment × channel counts |
| `07_adoption_tenure_value.png` | Adoption and tenure vs value |
| `08_status_by_channel.png` | Outcome mix by channel |
| `09_income_vs_value.png` | Income vs value scatter |
| `10_geography.png` | District counts, urbanity means |
| `11_correlation_heatmap.png` | Numeric Pearson correlations |
| `12_multivariate_and_outliers.png` | Segment × channel mean value, top-10 payments |
| `figure_index.txt` | Machine-readable list of the 12 figures |
