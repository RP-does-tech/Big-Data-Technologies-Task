"""
Stage 4 — Document-oriented analysis with MongoDB
==================================================

Imports the Stage 2 CSV data into MongoDB, creates indexes, and runs a set of
documented queries / aggregation pipelines. Results are printed and saved to
mongodb_outputs/query_results.txt.

Design summary
--------------
Database: digital_payments
Collections:
  customers          300 docs  (embedded demographic/adoption/preferences objects)
  locations          100 docs  (embedded GeoJSON Point + 2dsphere index)
  merchant_categories 10 docs  (lookup)
  payment_channels     6 docs  (lookup)
  transactions       5000 docs (references customer_id/location_id; embeds a
                                customer_snapshot and a value{currency,amount}
                                sub-document)

Run::

    python mongodb_stage4.py
"""

import csv
import json
import os
from datetime import datetime

from pymongo import MongoClient, ASCENDING, DESCENDING

# ---------------------------------------------------------------------------
# 0. Configuration
# ---------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUT_DIR = os.path.join(BASE_DIR, "mongodb_outputs")
os.makedirs(OUT_DIR, exist_ok=True)

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://127.0.0.1:27017")
DB_NAME = "digital_payments"

client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client[DB_NAME]

output_lines = []


def record(title, purpose, result):
    """Append a formatted query block to the results file and stdout."""
    output_lines.append("=" * 78)
    output_lines.append(title)
    output_lines.append("=" * 78)
    output_lines.append(f"PURPOSE: {purpose}")
    output_lines.append("")
    if hasattr(result, "explain"):  # defensive; not used for normal cursors
        result = list(result)
    if isinstance(result, (list, tuple)):
        payload = list(result)
    else:
        payload = [result]
    text = json.dumps(payload, indent=2, default=str, ensure_ascii=False)
    output_lines.append(text)
    output_lines.append("")
    print(title)
    print(f"PURPOSE: {purpose}")
    print(text)
    print()


def read_csv(filename):
    with open(os.path.join(DATA_DIR, filename), newline="",
              encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


# ---------------------------------------------------------------------------
# 1. Clean rebuild of the database
# ---------------------------------------------------------------------------

client.drop_database(DB_NAME)
db = client[DB_NAME]

print(f"Connected to MongoDB {client.server_info()['version']}")
print(f"Rebuilding database '{DB_NAME}'...\n")

# ---------------------------------------------------------------------------
# 2. Import: customers (embedding)
# ---------------------------------------------------------------------------

customer_docs = []
for row in read_csv("customers.csv"):
    customer_docs.append({
        "_id": row["customer_id"],
        "customer_id": row["customer_id"],
        "demographic": {
            "age": int(row["age"]),
            "gender": row["gender"],
            "occupation": row["occupation"],
        },
        "segment": row["customer_segment"],
        "adoption": {
            "level": row["adoption_level"],
            "tenure_months": int(row["adoption_tenure_months"]),
        },
        "monthly_income_bnd": int(row["monthly_income_bnd"]),
        "preferences": {
            "primary_payment_channel": row["primary_payment_channel"],
            "digital_payment_frequency": row["digital_payment_frequency"],
        },
    })
db.customers.insert_many(customer_docs)

# ---------------------------------------------------------------------------
# 3. Import: locations (embedding GeoJSON)
# ---------------------------------------------------------------------------

location_docs = []
for row in read_csv("locations.csv"):
    location_docs.append({
        "_id": row["location_id"],
        "location_id": row["location_id"],
        "district": row["district"],
        "area_name": row["area_name"],
        "urbanity": row["urbanity"],
        "country": row["country"],
        # GeoJSON order is [longitude, latitude], not [latitude, longitude].
        "geo": {
            "type": "Point",
            "coordinates": [
                float(row["longitude"]),
                float(row["latitude"]),
            ],
        },
    })
db.locations.insert_many(location_docs)

# ---------------------------------------------------------------------------
# 4. Import: lookup collections
# ---------------------------------------------------------------------------

category_docs = []
for row in read_csv("merchant_categories.csv"):
    category_docs.append({
        "_id": row["merchant_category"],
        "merchant_category": row["merchant_category"],
        "typical_min_value_bnd": int(row["typical_min_value_bnd"]),
        "typical_max_value_bnd": int(row["typical_max_value_bnd"]),
        "selection_weight": int(row["selection_weight"]),
    })
db.merchant_categories.insert_many(category_docs)

channel_docs = []
for row in read_csv("payment_channels.csv"):
    channel_docs.append({
        "_id": row["payment_channel"],
        "payment_channel": row["payment_channel"],
        "channel_id": row["channel_id"],
        "channel_description": row["channel_description"],
    })
db.payment_channels.insert_many(channel_docs)

# ---------------------------------------------------------------------------
# 5. Import: transactions (references + embedded snapshots)
# ---------------------------------------------------------------------------

transaction_docs = []
for row in read_csv("transactions.csv"):
    transaction_docs.append({
        "_id": row["transaction_id"],
        "transaction_id": row["transaction_id"],
        "customer_id": row["customer_id"],              # reference
        "location_id": row["location_id"],               # reference
        "transaction_datetime": datetime.strptime(
            row["transaction_datetime"], "%Y-%m-%d %H:%M:%S"
        ),
        "transaction_date": datetime.strptime(
            row["transaction_date"], "%Y-%m-%d"
        ),
        "transaction_hour": int(row["transaction_hour"]),
        "day_of_week": row["day_of_week"],
        "value": {                                       # embedded value object
            "amount": float(row["transaction_value_bnd"]),
            "currency": row["currency"],
        },
        "payment_channel": row["payment_channel"],       # natural-key reference
        "merchant_category": row["merchant_category"],   # natural-key reference
        "status": row["transaction_status"],
        "device_type": row["device_type"],
        "customer_snapshot": {                           # embedded, immutable
            "segment": row["customer_segment"],
            "adoption_level": row["adoption_level"],
            "adoption_tenure_months": int(row["adoption_tenure_months"]),
        },
        "cross_border": row["is_cross_border"] == "Yes",
    })
db.transactions.insert_many(transaction_docs)

# ---------------------------------------------------------------------------
# 6. Indexes
# ---------------------------------------------------------------------------

db.customers.create_index([("segment", ASCENDING),
                           ("adoption.level", ASCENDING)],
                          name="segment_adoption")
db.locations.create_index([("geo", "2dsphere")], name="geo_2dsphere")
db.locations.create_index([("district", ASCENDING),
                           ("urbanity", ASCENDING)], name="district_urbanity")
db.transactions.create_index([("customer_id", ASCENDING)],
                             name="customer_ref")
db.transactions.create_index([("location_id", ASCENDING)],
                             name="location_ref")
db.transactions.create_index([("transaction_date", ASCENDING),
                              ("status", ASCENDING)], name="date_status")
db.transactions.create_index([("merchant_category", ASCENDING),
                              ("transaction_date", DESCENDING)],
                             name="category_date")
db.transactions.create_index(
    [("customer_snapshot.segment", ASCENDING)], name="snapshot_segment"
)

counts = {name: db[name].count_documents({}) for name in [
    "customers", "locations", "merchant_categories",
    "payment_channels", "transactions",
]}
print("Collection counts:", counts)
print("Indexes created.\n")

# ---------------------------------------------------------------------------
# 7. Query 1 — inspect an embedded customer document
# ---------------------------------------------------------------------------

record(
    "Q1 | Find one customer by _id (embedded structure)",
    "Verify how demographic, adoption and preference fields are embedded.",
    db.customers.find_one({"_id": "C0001"}),
)

# ---------------------------------------------------------------------------
# 8. Query 2 — dot-notation filter on embedded fields
# ---------------------------------------------------------------------------

q2 = list(db.customers.find(
    {"adoption.level": "High", "monthly_income_bnd": {"$gte": 5000}},
    {"_id": 1, "segment": 1, "monthly_income_bnd": 1,
     "demographic.age": 1, "adoption.level": 1},
).sort("demographic.age", DESCENDING).limit(5))

record(
    "Q2 | High-adoption customers with income >= 5000 BND",
    "Find affluent, digitally adopted customers; sort by embedded age desc.",
    q2,
)

# ---------------------------------------------------------------------------
# 9. Query 3 — geospatial $near on the 2dsphere index
# ---------------------------------------------------------------------------

q3 = list(db.locations.find(
    {
        "geo": {
            "$near": {
                "$geometry": {
                    "type": "Point",
                    "coordinates": [114.94, 4.89],  # Bandar Seri Begawan area
                },
                "$maxDistance": 50000,             # metres
            }
        }
    },
    {"_id": 1, "area_name": 1, "district": 1, "urbanity": 1},
).limit(3))

record(
    "Q3 | Locations within 50 km of central Bandar Seri Begawan",
    "Demonstrate the GeoJSON Point + 2dsphere index for proximity lookup.",
    q3,
)

# ---------------------------------------------------------------------------
# 10. Query 4 — reference resolution with $lookup
# ---------------------------------------------------------------------------

q4 = list(db.transactions.aggregate([
    {"$match": {"customer_id": "C0001"}},
    {"$lookup": {
        "from": "customers",
        "localField": "customer_id",
        "foreignField": "_id",
        "as": "customer",
    }},
    {"$unwind": "$customer"},
    {"$project": {
        "_id": 0,
        "transaction_id": 1,
        "value": 1,
        "merchant_category": 1,
        "customer_segment": "$customer.segment",
        "customer_occupation": "$customer.demographic.occupation",
    }},
    {"$limit": 3},
]))

record(
    "Q4 | Resolve a transaction's customer reference with $lookup",
    "Join transactions to the customers collection instead of duplicating all "
    "customer fields in every transaction.",
    q4,
)

# ---------------------------------------------------------------------------
# 11. Aggregation A1 — multi-stage: $match > $group > $sort > $limit > $project
# ---------------------------------------------------------------------------

a1 = list(db.transactions.aggregate([
    {"$match": {
        "customer_snapshot.adoption_level": "High",
        "status": "Successful",
    }},
    {"$group": {
        "_id": "$merchant_category",
        "transactions": {"$sum": 1},
        "total_value": {"$sum": "$value.amount"},
        "avg_value": {"$avg": "$value.amount"},
        "max_value": {"$max": "$value.amount"},
    }},
    {"$sort": {"total_value": DESCENDING}},
    {"$limit": 5},
    {"$project": {
        "_id": 0,
        "merchant_category": "$_id",
        "transactions": 1,
        "total_value": {"$round": ["$total_value", 2]},
        "avg_value": {"$round": ["$avg_value", 2]},
        "max_value": {"$round": ["$max_value", 2]},
    }},
]))

record(
    "A1 | Successful high-adoption spend by merchant category (top 5)",
    "Aggregate successful payments made by High-adoption customers, rank "
    "categories by total BND value, and present rounded summary fields.",
    a1,
)

# ---------------------------------------------------------------------------
# 12. Aggregation A2 — channel usage with lookup and projection
# ---------------------------------------------------------------------------

a2 = list(db.transactions.aggregate([
    {"$group": {
        "_id": "$payment_channel",
        "transactions": {"$sum": 1},
        "total_value": {"$sum": "$value.amount"},
        "avg_value": {"$avg": "$value.amount"},
    }},
    {"$lookup": {
        "from": "payment_channels",
        "localField": "_id",
        "foreignField": "_id",
        "as": "channel",
    }},
    {"$unwind": "$channel"},
    {"$project": {
        "_id": 0,
        "payment_channel": "$_id",
        "channel_id": "$channel.channel_id",
        "transactions": 1,
        "avg_value": {"$round": ["$avg_value", 2]},
    }},
    {"$sort": {"transactions": DESCENDING}},
]))

record(
    "A2 | Payment-channel usage with lookup to the channel lookup collection",
    "Count and average value per channel, then enrich with the human-readable "
    "channel_id stored in the payment_channels collection.",
    a2,
)

# ---------------------------------------------------------------------------
# 13. Aggregation A3 — monthly trend ($group > $sort > $project)
# ---------------------------------------------------------------------------

a3 = list(db.transactions.aggregate([
    {"$group": {
        "_id": {"$month": "$transaction_date"},
        "transactions": {"$sum": 1},
        "total_value": {"$sum": "$value.amount"},
    }},
    {"$sort": {"_id": ASCENDING}},
    {"$project": {
        "_id": 0,
        "month": "$_id",
        "transactions": 1,
        "total_value": {"$round": ["$total_value", 2]},
    }},
]))

record(
    "A3 | Monthly transaction volume and value",
    "Derive the calendar month directly from the BSON date in the pipeline "
    "and produce a 12-row trend for 2025.",
    a3,
)

# ---------------------------------------------------------------------------
# 14. Save results
# ---------------------------------------------------------------------------

with open(os.path.join(OUT_DIR, "query_results.txt"), "w",
          encoding="utf-8") as handle:
    handle.write("\n".join(output_lines))

print(f"Query results saved to {os.path.join(OUT_DIR, 'query_results.txt')}")
print("Stage 4 complete.")
