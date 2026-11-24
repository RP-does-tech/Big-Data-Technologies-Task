"""
Stage 5 — Distributed analytical processing with Apache Spark SQL
=================================================================

Loads the Stage 2 CSVs into Spark DataFrames, registers them as temporary
views, and answers six substantive analytical questions using a mix of the
DataFrame API and Spark SQL. All queries include filtering, grouping and
aggregation; several include joins with the supporting dimensions.

Outputs
-------
spark_outputs/query_results.txt   Full code/question/result log
spark_outputs/answer_1.csv ...    Result tables (one per question, via Pandas)

Run::

    python spark_stage5.py
"""

import os

from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F

# ---------------------------------------------------------------------------
# 0. Spark session
# ---------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUT_DIR = os.path.join(BASE_DIR, "spark_outputs")
os.makedirs(OUT_DIR, exist_ok=True)

spark = (
    SparkSession.builder
    .appName("Stage5-DigitalPayment-SparkSQL")
    .master("local[*]")
    .config("spark.sql.shuffle.partitions", "8")
    .config("spark.ui.enabled", "false")
    .getOrCreate()
)
spark.sparkContext.setLogLevel("ERROR")

print(f"Spark version: {spark.version}")


def load_csv(name):
    return (
        spark.read
        .option("header", "true")
        .option("inferSchema", "true")
        .csv(os.path.join(DATA_DIR, name))
    )


transactions = load_csv("transactions.csv")
customers = load_csv("customers.csv")
locations = load_csv("locations.csv")
categories = load_csv("merchant_categories.csv")
channels = load_csv("payment_channels.csv")

transactions.createOrReplaceTempView("transactions")
customers.createOrReplaceTempView("customers")
locations.createOrReplaceTempView("locations")
categories.createOrReplaceTempView("merchant_categories")
channels.createOrReplaceTempView("payment_channels")

print("Row counts:", {
    "transactions": transactions.count(),
    "customers": customers.count(),
    "locations": locations.count(),
    "categories": categories.count(),
    "channels": channels.count(),
})

output_lines = []


def present(number, title, question, code, dataframe, limit=20):
    """Save a result table to CSV and append its question/code/result to the log."""
    pdf = dataframe.limit(limit).toPandas()
    csv_path = os.path.join(OUT_DIR, f"answer_{number}.csv")
    pdf.to_csv(csv_path, index=False)

    rendered = dataframe.limit(limit).toPandas().to_string(index=False)
    block = [
        "=" * 82,
        f"ANSWER {number} | {title}",
        "=" * 82,
        f"QUESTION: {question}",
        "",
        "CODE:",
        code.strip(),
        "",
        "RESULT:",
        rendered,
        "",
        f"(saved CSV: {csv_path})",
        "",
    ]
    text = "\n".join(block)
    output_lines.append(text)
    print(text)


# ---------------------------------------------------------------------------
# Q1 — Digital-first behaviour by segment (join + filter + group)
# ---------------------------------------------------------------------------

q1_code = """
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
    .orderBy(F.desc("digital_first_pct"))
)
"""
answer_1 = (
    transactions.filter(F.col("transaction_status") == "Successful")
    .join(customers.select("customer_id", "monthly_income_bnd"), "customer_id")
    .withColumn(
        "is_digital_first",
        F.col("payment_channel").isin(["Mobile Wallet", "QR Payment"]).cast("int"),
    )
    .groupBy("customer_segment")
    .agg(
        F.count("*").alias("transactions"),
        F.round(F.avg("is_digital_first") * 100, 1).alias("digital_first_pct"),
        F.round(F.avg("transaction_value_bnd"), 2).alias("avg_value_bnd"),
        F.round(F.avg("monthly_income_bnd"), 0).alias("avg_income_bnd"),
    )
    .orderBy(F.desc("digital_first_pct"))
)

present(
    1,
    "Digital-first channel usage by customer segment",
    "Which segments rely most on digital-first rails (wallet/QR), and how does "
    "that compare with their average income and average payment value?",
    q1_code,
    answer_1,
)

# ---------------------------------------------------------------------------
# Q2 — Category revenue and failure rate (Spark SQL, HAVING)
# ---------------------------------------------------------------------------

q2_code = """
answer_2 = spark.sql(\"\"\"
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
\"\"\")
"""
answer_2 = spark.sql("""
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
""")

present(
    2,
    "Merchant-category revenue and failure rate",
    "Which merchant categories contribute the most successful value, and do "
    "any categories show a notably higher failure rate? Only categories with "
    "at least 100 transactions are compared.",
    q2_code,
    answer_2,
)

# ---------------------------------------------------------------------------
# Q3 — Time-of-day x urbanity (join + bucketing + group)
# ---------------------------------------------------------------------------

q3_code = """
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
    .orderBy("hour_bucket", "urbanity")
)
"""
answer_3 = (
    transactions.filter(F.col("transaction_status") == "Successful")
    .join(locations.select("location_id", "urbanity", "district"), "location_id")
    .withColumn(
        "hour_bucket",
        F.when(F.col("transaction_hour") < 12, "Morning")
        .when(F.col("transaction_hour") < 17, "Afternoon")
        .otherwise("Evening"),
    )
    .groupBy("hour_bucket", "urbanity")
    .agg(
        F.count("*").alias("transactions"),
        F.round(F.sum("transaction_value_bnd"), 2).alias("total_value_bnd"),
        F.round(F.avg("transaction_value_bnd"), 2).alias("avg_value_bnd"),
    )
    .orderBy("hour_bucket", "urbanity")
)

present(
    3,
    "Time-of-day and urbanity interaction",
    "How do transaction volume and value differ across morning/afternoon/"
    "evening and across urban, suburban and rural locations?",
    q3_code,
    answer_3,
)

# ---------------------------------------------------------------------------
# Q4 — High-value cross-border payments (Spark SQL join + filters)
# ---------------------------------------------------------------------------

q4_code = """
answer_4 = spark.sql(\"\"\"
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
\"\"\")
"""
answer_4 = spark.sql("""
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
""")

present(
    4,
    "High-value cross-border payments by district and channel",
    "Where and through which payment rails do successful cross-border "
    "payments of at least 500 BND occur?",
    q4_code,
    answer_4,
)

# ---------------------------------------------------------------------------
# Q5 — Top-value customers per segment (window function)
# ---------------------------------------------------------------------------

max_date = transactions.select(F.max(F.to_date("transaction_date"))).first()[0]

q5_code = """
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
    .orderBy("customer_segment", "rank_in_segment")
)
"""
win = Window.partitionBy("customer_segment").orderBy(F.desc("monetary"))
answer_5 = (
    transactions.filter(F.col("transaction_status") == "Successful")
    .groupBy("customer_id")
    .agg(
        F.count("*").alias("frequency"),
        F.round(F.sum("transaction_value_bnd"), 2).alias("monetary"),
        F.max(F.to_date("transaction_date")).alias("last_payment"),
    )
    .join(
        customers.select("customer_id", "customer_segment", "monthly_income_bnd"),
        "customer_id",
    )
    .withColumn("recency_days", F.datediff(F.lit(max_date), F.col("last_payment")))
    .withColumn("rank_in_segment", F.rank().over(win))
    .filter(F.col("rank_in_segment") <= 5)
    .select(
        "customer_id", "customer_segment", "frequency", "monetary",
        "recency_days", "monthly_income_bnd", "rank_in_segment",
    )
    .orderBy("customer_segment", "rank_in_segment")
)

present(
    5,
    "Top-value customers within each segment (RFM-style)",
    "Who are the five highest-spend successful customers in each segment, "
    "and how recently did they pay? This combines frequency, monetary value "
    "and recency with a per-segment window ranking.",
    q5_code,
    answer_5,
    limit=25,
)

# ---------------------------------------------------------------------------
# Q6 — Channel x device success rate (filter + group + derived rate)
# ---------------------------------------------------------------------------

q6_code = """
answer_6 = (
    transactions
    .groupBy("payment_channel", "device_type")
    .agg(F.count("*").alias("transactions"),
         F.round(100 * F.avg((F.col("transaction_status") == "Successful")
                             .cast("int")), 2).alias("success_pct"),
         F.round(F.avg("transaction_value_bnd"), 2).alias("avg_value_bnd"))
    .filter(F.col("transactions") >= 50)
    .orderBy(F.desc("success_pct"))
)
"""
answer_6 = (
    transactions.groupBy("payment_channel", "device_type")
    .agg(
        F.count("*").alias("transactions"),
        F.round(
            100 * F.avg((F.col("transaction_status") == "Successful").cast("int")),
            2,
        ).alias("success_pct"),
        F.round(F.avg("transaction_value_bnd"), 2).alias("avg_value_bnd"),
    )
    .filter(F.col("transactions") >= 50)
    .orderBy(F.desc("success_pct"))
)

present(
    6,
    "Success rate by channel and device combination",
    "Do payment success rates differ across channel/device pairs, after "
    "ignoring combinations with fewer than 50 observations?",
    q6_code,
    answer_6,
)

# ---------------------------------------------------------------------------
# Save log and stop
# ---------------------------------------------------------------------------

with open(os.path.join(OUT_DIR, "query_results.txt"), "w",
          encoding="utf-8") as handle:
    handle.write("\n".join(output_lines))

print(f"Log saved to {os.path.join(OUT_DIR, 'query_results.txt')}")
spark.stop()
print("Stage 5 complete.")
