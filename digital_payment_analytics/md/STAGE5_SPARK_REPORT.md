# Stage 5 — Distributed Analytical Processing with Apache Spark SQL

**Engine:** Apache Spark 4.3.0 (PySpark), local `[*]` mode, Java 17  
**Script:** `spark_stage5.py`  
**Outputs:** `spark_outputs/query_results.txt`, `spark_outputs/answer_1.csv` … `answer_6.csv`

---

## 1. Loading and preparation

All five Stage 2 CSVs are read into Spark DataFrames with header inference and registered as temporary SQL views:

| View / DataFrame | Rows | Use |
|---|---:|---|
| `transactions` | 5,000 | Main fact table |
| `customers` | 300 | Customer dimension (join) |
| `locations` | 100 | Location dimension (join) |
| `merchant_categories` | 10 | Lookup |
| `payment_channels` | 6 | Lookup |

Spark session settings used for this local run:

```python
spark = (SparkSession.builder
         .appName("Stage5-DigitalPayment-SparkSQL")
         .master("local[*]")
         .config("spark.sql.shuffle.partitions", "8")
         .config("spark.ui.enabled", "false")
         .getOrCreate())
spark.sparkContext.setLogLevel("ERROR")
```

The analyses deliberately mix the **DataFrame API** (Q1, Q3, Q5, Q6) and **Spark SQL** (Q2, Q4) to demonstrate both interfaces over the same registered views.

**Environment note:** Spark emitted non-fatal warnings about missing `winutils.exe` and limited pandas 3.0 support in local Windows mode. All jobs completed successfully, and every answer was cross-checked against an independent pandas calculation of the same logic.

### Why these operations are useful

* **Filtering early** (`transaction_status == 'Successful'`, minimum value thresholds, minimum group sizes) reduces the number of rows carried into shuffles and removes noise before aggregation.
* **Grouping/aggregation** (`groupBy` / `GROUP BY`, `count`, `sum`, `avg`, conditional rates) turns 5,000 raw events into decision-ready metrics at the grain of a segment, category, district or time bucket.
* **Joins** attach dimension attributes (income, urbanity, district, segment) that are not stored in full on every transaction, mirroring a fact/dimension model.
* **Window functions** rank customers *within* each segment without collapsing the result to one global ranking — useful for per-cohort top-N lists.
* These operations are identical in code whether the data is 5,000 rows locally or billions of rows on a cluster; only the cluster configuration changes.

---

## 2. Analytical questions, code, results and interpretation

### Q1 — Digital-first channel usage by customer segment

**Question:** Which segments rely most on digital-first rails (Mobile Wallet + QR Payment), and how does that compare with average income and payment value?

```python
digital = ["Mobile Wallet", "QR Payment"]
answer_1 = (
    transactions.filter(F.col("transaction_status") == "Successful")
    .join(customers.select("customer_id", "monthly_income_bnd"), "customer_id")
    .withColumn("is_digital_first",
                F.col("payment_channel").isin(digital).cast("int"))
    .groupBy("customer_segment")
    .agg(F.count("*").alias("transactions"),
         F.round(F.avg("is_digital_first") * 100, 1).alias("digital_first_pct"),
         F.round(F.avg("transaction_value_bnd"), 2).alias("avg_value_bnd"),
         F.round(F.avg("monthly_income_bnd"), 0).alias("avg_income_bnd"))
    .orderBy(F.desc("digital_first_pct")))
```

**Result summary**

| customer_segment | transactions | digital_first_pct | avg_value_bnd | avg_income_bnd |
|---|---:|---:|---:|---:|
| Tech Savvy | 858 | 66.2 | 166.16 | 2,973 |
| Young Professionals | 1,364 | 47.1 | 162.41 | 2,876 |
| Working Adults | 1,079 | 33.6 | 156.75 | 2,813 |
| Traditional Users | 847 | 16.3 | 167.12 | 2,981 |
| Senior Citizens | 550 | 13.3 | 154.11 | 3,118 |

**Interpretation:** There is a clear gradient: Tech Savvy customers use wallet/QR for about two-thirds of successful payments, while Senior Citizens do so for roughly one in eight. This mirrors the segment-specific channel weights built into the Stage 2 generator. Notably, average income does **not** follow the same gradient — Senior Citizens have the highest average income band yet the lowest digital-first share — so income alone would be a poor proxy for digital channel preference in this dataset. The join to `customers` is needed only for `monthly_income_bnd`; the segment itself is already on the transaction.

---

### Q2 — Merchant-category revenue and failure rate

**Question:** Which categories contribute the most successful value, and do any show elevated failure rates? (Categories with ≥100 transactions only.)

```sql
SELECT merchant_category,
       COUNT(*) AS transactions,
       ROUND(SUM(CASE WHEN transaction_status='Successful'
                      THEN transaction_value_bnd ELSE 0 END), 2) AS successful_value_bnd,
       ROUND(AVG(transaction_value_bnd), 2) AS avg_value_bnd,
       ROUND(100.0 * SUM(CASE WHEN transaction_status='Failed' THEN 1 ELSE 0 END)
             / COUNT(*), 2) AS failure_pct
FROM transactions
GROUP BY merchant_category
HAVING COUNT(*) >= 100
ORDER BY failure_pct DESC
```

**Result summary**

| merchant_category | transactions | successful_value_bnd | avg_value_bnd | failure_pct |
|---|---:|---:|---:|---:|
| Online Shopping | 347 | 68,225.65 | 217.92 | 7.20 |
| Healthcare | 255 | 38,889.02 | 167.28 | 7.06 |
| Entertainment | 290 | 29,451.01 | 109.65 | 5.86 |
| Grocery | 899 | 67,307.36 | 80.01 | 5.23 |
| Utilities | 420 | 104,183.03 | 270.23 | 5.00 |
| Retail | 816 | 200,659.99 | 262.33 | 3.68 |
| Education | 225 | 52,556.92 | 248.64 | 3.11 |
| Transportation | 625 | 16,008.33 | 27.05 | 2.40 |
| Restaurant | 949 | 48,834.07 | 53.73 | 2.32 |
| Travel | 174 | 133,417.67 | 796.52 | 2.30 |

**Interpretation:** Failure rates are highest for Online Shopping (7.20%) and Healthcare (7.06%), but the spread is modest (2.30–7.20%) and the overall failure rate is only ~4%. With only 174 Travel transactions, its 2.30% failure rate is based on ~4 failures, so it should not be over-interpreted. Revenue tells a different story: **Retail** generates the most successful value (200,660 BND) through volume, while **Travel** generates 133,418 BND from only 174 high-ticket payments. `HAVING COUNT(*) >= 100` keeps tiny groups from distorting the rate comparison. The conditional `SUM(CASE ...)` is the useful Spark SQL idiom for computing a rate in the same pass as the totals.

---

### Q3 — Time-of-day and urbanity interaction

**Question:** How do volume and value differ across morning/afternoon/evening and urban/suburban/rural locations?

```python
answer_3 = (
    transactions.filter(F.col("transaction_status") == "Successful")
    .join(locations.select("location_id", "urbanity", "district"), "location_id")
    .withColumn("hour_bucket",
         F.when(F.col("transaction_hour") < 12, "Morning")
          .when(F.col("transaction_hour") < 17, "Afternoon")
          .otherwise("Evening"))
    .groupBy("hour_bucket", "urbanity")
    .agg(F.count("*").alias("transactions"),
         F.round(F.sum("transaction_value_bnd"), 2).alias("total_value_bnd"),
         F.round(F.avg("transaction_value_bnd"), 2).alias("avg_value_bnd"))
    .orderBy("hour_bucket", "urbanity"))
```

**Result summary**

| hour_bucket | urbanity | transactions | total_value_bnd | avg_value_bnd |
|---|---|---:|---:|---:|
| Afternoon | Rural | 110 | 23,722.71 | 215.66 |
| Afternoon | Suburban | 187 | 33,311.55 | 178.14 |
| Afternoon | Urban | 1,304 | 204,500.14 | 156.83 |
| Evening | Rural | 124 | 17,522.21 | 141.31 |
| Evening | Suburban | 181 | 31,977.80 | 176.67 |
| Evening | Urban | 1,488 | 238,378.91 | 160.20 |
| Morning | Rural | 98 | 14,133.80 | 144.22 |
| Morning | Suburban | 111 | 18,643.36 | 167.96 |
| Morning | Urban | 1,095 | 177,342.57 | 161.96 |

*(The script orders by `hour_bucket`, so labels appear alphabetically: Afternoon, Evening, Morning.)*

**Interpretation:** Urban locations dominate every time bucket (~1,100–1,500 payments vs 98–187 elsewhere) because of the location sampling weights in Stage 2. The **evening urban** slot is the single largest cell (1,488 payments, 238,379 BND). Average values are fairly flat across buckets (141–216 BND); the highest rural afternoon average (215.66) is based on only 110 payments, so it is much less stable than the urban averages. This is a useful reminder that aggregated rates on small groups need volume context. The join to `locations` is essential here because `urbanity` is not a transaction attribute.

---

### Q4 — High-value cross-border payments by district and channel

**Question:** Where and through which rails do successful cross-border payments of at least 500 BND occur?

```sql
SELECT l.district, t.payment_channel,
       COUNT(*) AS cross_border_tx,
       ROUND(SUM(t.transaction_value_bnd), 2) AS total_value_bnd
FROM transactions t
JOIN locations l ON t.location_id = l.location_id
WHERE t.transaction_status = 'Successful'
  AND t.is_cross_border = 'Yes'
  AND t.transaction_value_bnd >= 500
GROUP BY l.district, t.payment_channel
ORDER BY total_value_bnd DESC
```

**Result summary (all 8 groups)**

| district | payment_channel | cross_border_tx | total_value_bnd |
|---|---|---:|---:|
| Brunei-Muara | Mobile Wallet | 2 | 2,150.40 |
| Belait | Mobile Wallet | 2 | 2,086.55 |
| Belait | Online Banking | 1 | 1,642.25 |
| Tutong | Mobile Wallet | 1 | 1,593.76 |
| Brunei-Muara | Credit Card | 2 | 1,310.31 |
| Brunei-Muara | QR Payment | 1 | 1,119.86 |
| Belait | Credit Card | 1 | 763.31 |
| Tutong | QR Payment | 1 | 525.13 |

**Interpretation:** Only **11 transactions** satisfy all three filters, so this analysis is deliberately narrow. Mobile Wallet appears in three of the top four groups and accounts for the two largest totals, but with counts of 1–2 per group these are **indicative, not stable patterns**. The value of the query is demonstrating a multi-condition filter combined with a fact-to-dimension join: neither `district` nor the boolean cross-border flag alone would answer the business question. No Temburong groups appear because none of its (few) transactions met the high-value cross-border condition.

---

### Q5 — Top-value customers within each segment (RFM-style)

**Question:** Who are the five highest-spend successful customers in each segment, and how recently did they pay?

```python
win = Window.partitionBy("customer_segment").orderBy(F.desc("monetary"))
answer_5 = (
    transactions.filter(F.col("transaction_status") == "Successful")
    .groupBy("customer_id")
    .agg(F.count("*").alias("frequency"),
         F.round(F.sum("transaction_value_bnd"), 2).alias("monetary"),
         F.max(F.to_date("transaction_date")).alias("last_payment"))
    .join(customers.select("customer_id", "customer_segment",
                           "monthly_income_bnd"), "customer_id")
    .withColumn("recency_days", F.datediff(F.lit(max_date), F.col("last_payment")))
    .withColumn("rank_in_segment", F.rank().over(win))
    .filter(F.col("rank_in_segment") <= 5)
    .select("customer_id", "customer_segment", "frequency", "monetary",
            "recency_days", "monthly_income_bnd", "rank_in_segment")
    .orderBy("customer_segment", "rank_in_segment"))
```

**Result summary — rank 1 in each segment (full 25-row table in `spark_outputs/answer_5.csv`)**

| customer_id | segment | frequency | monetary (BND) | recency_days | income band | rank |
|---|---|---:|---:|---:|---:|---:|
| C0198 | Senior Citizens | 27 | 4,770.50 | 3 | 6,000 | 1 |
| C0300 | Tech Savvy | 25 | 7,042.82 | 1 | 5,000 | 1 |
| C0069 | Traditional Users | 19 | 4,996.15 | 13 | 2,000 | 1 |
| C0268 | Working Adults | 20 | 6,600.31 | 1 | 6,000 | 1 |
| C0171 | Young Professionals | 23 | 6,428.45 | 30 | 4,000 | 1 |

**Interpretation:** Tech Savvy and Working Adults have the highest top-customer monetary totals (~7.0k and ~6.6k BND). Recency is short for most leaders (1–13 days), except the top Young Professional (30 days). A window function is the right tool here: it ranks within each `customer_segment` partition and keeps five rows per cohort, which a single global `ORDER BY ... LIMIT 5` could not do. The join adds the segment label that is not needed for the aggregation itself but is essential for partitioning and reporting.

---

### Q6 — Success rate by channel and device combination

**Question:** Do success rates differ across channel/device pairs (excluding pairs with fewer than 50 observations)?

```python
answer_6 = (
    transactions.groupBy("payment_channel", "device_type")
    .agg(F.count("*").alias("transactions"),
         F.round(100 * F.avg((F.col("transaction_status") == "Successful")
                             .cast("int")), 2).alias("success_pct"),
         F.round(F.avg("transaction_value_bnd"), 2).alias("avg_value_bnd"))
    .filter(F.col("transactions") >= 50)
    .orderBy(F.desc("success_pct")))
```

**Result summary (top 6 of 13 qualifying pairs)**

| payment_channel | device_type | transactions | success_pct | avg_value_bnd |
|---|---|---:|---:|---:|
| Bank Transfer | Computer | 250 | 96.00 | 138.60 |
| Bank Transfer | POS Terminal | 250 | 96.00 | 150.29 |
| Debit Card | Smartphone | 327 | 95.72 | 160.11 |
| Online Banking | Smartphone | 296 | 94.93 | 180.37 |
| Credit Card | Smartphone | 266 | 94.36 | 159.40 |
| QR Payment | Smartphone | 939 | 94.25 | 163.35 |

*Full result includes 13 pairs; the lowest is Credit Card / POS Terminal at 91.46% over 246 transactions.*

**Interpretation:** Success rates span roughly 91.5–96.0%, a ~4.5 percentage-point range across sufficiently large groups. Bank Transfer on Computer/POS sits at the top, while card-on-POS combinations sit at the bottom. Because the Stage 2 generator assigned status independently of channel and device (94/4/2 overall), these differences are almost certainly **sampling variation**, not a real performance difference. The exercise still demonstrates a useful pattern: compute a Boolean-derived rate with `avg(cast(condition as int))` and apply a minimum-support filter so small cells do not produce misleading extremes.

---

## 3. Cross-stage consistency and caveats

* Q1 and Q3 reproduce the segment-channel and urbanity patterns seen in MongoDB Stage 4 and pandas Stage 3, confirming the Spark reads are faithful to the CSVs.
* Q2 and Q6 show small rate differences that are consistent with sampling noise, not causal effects.
* Q4 is based on only 11 transactions and Q5's rankings on 18–27 payments per customer; both are directional only.
* As before, all findings are **descriptive**. The Stage 2 generator explicitly programmed segment→channel, category→value and income→value rules, so Spark is rediscovering design assumptions rather than establishing real-world causality.

---

## 4. Reproduce

```powershell
cd "C:\Users\ASUS\Documents\Big Data Tech Task"
python digital_payment_analytics\spark_stage5.py
```

Requirements: Python 3.13, Java 17+, `pyspark` (`python -m pip install pyspark`). The script prints every result, writes the full log to `spark_outputs/query_results.txt`, and exports each answer table to `spark_outputs/answer_N.csv`.
