# Stage 4 — Document-Oriented Analysis with MongoDB

**Server:** MongoDB 9.0.2 at `mongodb://127.0.0.1:27017` (local, no authentication)  
**Database:** `digital_payments`  
**Script:** `mongodb_stage4.py`  
**Raw output:** `mongodb_outputs/query_results.txt`

The script rebuilds the database from the Stage 2 CSVs on every run (`drop_database` → create → insert → index → query), so it is idempotent and reproducible.

---

## 1. Collections and document design

| Collection | Docs | Role | Key |
|---|---:|---|---|
| `customers` | 300 | Customer master / dimension | `_id` = `customer_id` (e.g. `C0001`) |
| `locations` | 100 | Location dimension with GeoJSON point | `_id` = `location_id` (e.g. `L001`) |
| `merchant_categories` | 10 | Controlled vocabulary + value rules | natural key `_id` = category name |
| `payment_channels` | 6 | Controlled vocabulary + channel descriptions | natural key `_id` = channel name |
| `transactions` | 5,000 | Main fact collection | `_id` = `transaction_id` (e.g. `T000001`) |

### 1.1 Example document — `customers`

```json
{
  "_id": "C0001",
  "customer_id": "C0001",
  "demographic": { "age": 35, "gender": "Male", "occupation": "Private Sector" },
  "segment": "Working Adults",
  "adoption": { "level": "Medium", "tenure_months": 18 },
  "monthly_income_bnd": 1500,
  "preferences": {
    "primary_payment_channel": "Mobile Wallet",
    "digital_payment_frequency": "Daily"
  }
}
```

**Embedded** `demographic`, `adoption` and `preferences`: these fields are read together for profiling, are small, bounded (one value each) and change rarely. Embedding keeps a customer profile in one document and allows filters such as `{"adoption.level": "High"}`.

### 1.2 Example document — `locations`

```json
{
  "_id": "L001",
  "location_id": "L001",
  "district": "Brunei-Muara",
  "area_name": "Muara",
  "urbanity": "Urban",
  "country": "Brunei Darussalam",
  "geo": { "type": "Point", "coordinates": [115.02942, 4.50711] }
}
```

**Embedded** `geo` is a GeoJSON Point in `[longitude, latitude]` order. A `2dsphere` index on `geo` supports `$near` proximity queries (Q3).

### 1.3 Example document — `transactions`

```json
{
  "_id": "T000002",
  "transaction_id": "T000002",
  "customer_id": "C0001",
  "location_id": "L021",
  "transaction_datetime": "2025-02-09T07:33:43",
  "transaction_date": "2025-02-09T00:00:00",
  "transaction_hour": 7,
  "day_of_week": "Sunday",
  "value": { "amount": 12.83, "currency": "BND" },
  "payment_channel": "QR Payment",
  "merchant_category": "Retail",
  "status": "Successful",
  "device_type": "Smartphone",
  "customer_snapshot": {
    "segment": "Working Adults",
    "adoption_level": "Medium",
    "adoption_tenure_months": 18
  },
  "cross_border": false
}
```

**Embedding choices in transactions**

* `value: {amount, currency}` — money is an atomic concept; keeping currency with the amount prevents a transaction from being interpreted without its denomination.
* `customer_snapshot` — segment/adoption/tenure are copied **at the moment of payment**. This preserves point-in-time truth for analytics even if the customer master is later corrected, and it lets common filters avoid a join. This is a deliberately immutable snapshot, unlike the live customer document.

**Referencing choices**

* `customer_id → customers._id` and `location_id → locations._id` — customer/location attributes are shared by many transactions and may be updated independently; storing only the key avoids update anomalies and duplication.
* `payment_channel` and `merchant_category` are natural-key references to the two lookup collections. Their descriptions/ranges live in one place and can be pulled in with `$lookup` (Q4, A2).
* The original CSV's `is_cross_border = "Yes"/"No"` is stored as a real boolean `cross_border`, and value/currency are a nested object — a clean example of reshaping flat CSV data to a document model.

### 1.4 Indexes

| Collection | Index | Reason |
|---|---|---|
| `customers` | `{segment:1, "adoption.level":1}` | Segment/adoption profiling (Q2) |
| `locations` | `{geo:"2dsphere"}` | Proximity query `$near` (Q3) |
| `locations` | `{district:1, urbanity:1}` | Geographic grouping |
| `transactions` | `{customer_id:1}` | Customer join/reference (Q4) |
| `transactions` | `{location_id:1}` | Location reference |
| `transactions` | `{transaction_date:1, status:1}` | Date/status filters (A1, A3) |
| `transactions` | `{merchant_category:1, transaction_date:-1}` | Category trend queries |
| `transactions` | `{"customer_snapshot.segment":1}` | Denormalised segment analytics |

---

## 2. Meaningful queries — purpose and interpreted output

### Q1 — Find one customer by `_id`

```javascript
db.customers.find_one({ _id: "C0001" })
```

**Purpose:** Confirm that the embedded profile document imports correctly and can be retrieved without any join.

**Interpreted output:** Customer `C0001` is a 35-year-old male in the Private Sector, segment **Working Adults**, **Medium** adoption with **18 months** tenure, monthly income **1,500 BND**, preferring **Mobile Wallet** and describing his digital-payment frequency as **Daily**. All profile information is in one document, as designed.

### Q2 — High-adoption, high-income customers

```javascript
db.customers.find(
  { "adoption.level": "High", "monthly_income_bnd": { "$gte": 5000 } },
  { segment: 1, monthly_income_bnd: 1, "demographic.age": 1, "adoption.level": 1 }
).sort({ "demographic.age": -1 }).limit(5)
```

**Purpose:** Locate affluent, digitally adopted customers using dot notation on embedded fields, with projection and sorting.

**Interpreted output (top 5):**

| customer_id | Age | Segment | Adoption | Income (BND) |
|---|---:|---|---|---:|
| C0079 | 38 | Young Professionals | High | 6,000 |
| C0185 | 37 | Young Professionals | High | 6,000 |
| C0170 | 37 | Young Professionals | High | 5,000 |
| C0293 | 36 | Young Professionals | High | 6,000 |
| C0151 | 35 | Young Professionals | High | 6,000 |

All five matches are **Young Professionals**. In this synthetic dataset the segment rules tie Young Professionals to High adoption and allow incomes up to 6,000 BND, so the concentration reflects the generator's design, not an independent market insight. The query demonstrates that embedded fields are filterable and sortable exactly like top-level fields.

### Q3 — Locations near central Bandar Seri Begawan

```javascript
db.locations.find({
  geo: { $near: {
    $geometry: { type: "Point", coordinates: [114.94, 4.89] },
    $maxDistance: 50000
  }}
}, { area_name: 1, district: 1, urbanity: 1 }).limit(3)
```

**Purpose:** Exercise the `2dsphere` index and the GeoJSON Point to answer a proximity question directly in MongoDB.

**Interpreted output (nearest 3):**

| location_id | Area | District | Urbanity |
|---|---|---|---|
| L072 | Labu | Temburong | Suburban |
| L068 | Kiulap | Brunei-Muara | Urban |
| L096 | Kiulap | Brunei-Muara | Urban |

The index returns three points within 50 km of the search point. Because Stage 2 generated coordinates by uniform sampling inside a bounding box rather than by real geocoding, a Temburong-labelled point can appear nearest to a central-Bandar coordinate. The query mechanics are valid; the **geographic labels should not be trusted for real spatial analysis** — a known synthetic-data limitation also noted in Stage 3.

### Q4 — Resolve a transaction reference with `$lookup`

```javascript
db.transactions.aggregate([
  { $match: { customer_id: "C0001" } },
  { $lookup: { from: "customers", localField: "customer_id",
               foreignField: "_id", as: "customer" } },
  { $unwind: "$customer" },
  { $project: { transaction_id: 1, value: 1, merchant_category: 1,
                customer_segment: "$customer.segment",
                customer_occupation: "$customer.demographic.occupation" } },
  { $limit: 3 }
])
```

**Purpose:** Show how the referenced customer document is joined back when full customer detail is needed, avoiding permanent duplication in every transaction.

**Interpreted output:** Transactions `T000002` (12.83 BND, Retail), `T000189` (58.37 BND, Restaurant) and `T000627` (145.59 BND, Retail) are all enriched with `customer_segment = "Working Adults"` and `customer_occupation = "Private Sector"` from `C0001`. The join works as intended; note that each transaction also carries its own `customer_snapshot`, so this lookup is only required for attributes that were *not* snapshotted (here, occupation).

---

## 3. Aggregation pipelines

### A1 — Multi-stage: `$match → $group → $sort → $limit → $project`

**Purpose:** Find the merchant categories generating the most successful spend among **High-adoption** customers, and present a tidy, rounded summary.

```javascript
db.transactions.aggregate([
  { $match: { "customer_snapshot.adoption_level": "High",
              "status": "Successful" } },
  { $group: { _id: "$merchant_category",
              transactions: { $sum: 1 },
              total_value: { $sum: "$value.amount" },
              avg_value: { $avg: "$value.amount" },
              max_value: { $max: "$value.amount" } } },
  { $sort: { total_value: -1 } },
  { $limit: 5 },
  { $project: { _id: 0, merchant_category: "$_id", transactions: 1,
                total_value: { $round: ["$total_value", 2] },
                avg_value: { $round: ["$avg_value", 2] },
                max_value: { $round: ["$max_value", 2] } } }
])
```

**Stage explanation**

1. `$match` — keep only successful payments by High-adoption customers (using the embedded snapshot, so no join).
2. `$group` — collapse to one document per merchant category; count rows and compute total, average and maximum of the embedded `value.amount`.
3. `$sort` — rank by `total_value` descending.
4. `$limit` — retain the top five categories.
5. `$project` — rename `_id`, round monetary fields to 2 decimals and suppress the internal key.

**Interpreted output**

| Merchant category | Transactions | Total value (BND) | Avg value (BND) | Max (BND) |
|---|---:|---:|---:|---:|
| Retail | 360 | 93,626.23 | 260.07 | 610.27 |
| Travel | 87 | 67,878.65 | 780.21 | 1,650.73 |
| Utilities | 179 | 48,768.10 | 272.45 | 615.58 |
| Grocery | 404 | 32,852.27 | 81.32 | 187.02 |
| Online Shopping | 153 | 32,847.18 | 214.69 | 508.88 |

**Interpretation:** Retail leads on **total** value mainly because it has many transactions (360), whereas Travel has only 87 payments but by far the highest **average** (780.21 BND) and the largest single payment (1,650.73 BND). Grocery has the most transactions of all (404) yet ranks fourth on value because its average is only 81.32 BND. This volume-vs-value contrast is consistent with the category value ranges identified in Stage 3 (`Travel` 50–1,500, `Grocery` 5–150). It is a property of the synthetic generator, not a causal finding.

### A2 — `$group → $lookup → $unwind → $project → $sort`

**Purpose:** Summarise usage of each payment channel and enrich it with the `channel_id` stored in the separate lookup collection.

**Interpreted output**

| Payment channel | channel_id | Transactions | Avg value (BND) |
|---|---|---:|---:|
| Debit Card | PC03 | 1,005 | 164.58 |
| Mobile Wallet | PC01 | 963 | 168.09 |
| QR Payment | PC02 | 939 | 163.35 |
| Credit Card | PC04 | 762 | 154.97 |
| Bank Transfer | PC06 | 723 | 150.07 |
| Online Banking | PC05 | 608 | 172.28 |

**Interpretation:** Debit Card is the most frequently used rail, but online banking carries the highest average payment. Average values are tightly clustered (150.07–172.28 BND), supporting the Stage 3 finding that channel is not strongly associated with amount in this dataset. The `$lookup` successfully resolves each natural key to its `channel_id`, illustrating the referencing design.

### A3 — `$group → $sort → $project` with date extraction

**Purpose:** Produce a 12-row monthly trend for 2025, deriving the month server-side from the BSON `transaction_date`.

**Interpreted output**

| Month | Transactions | Total value (BND) |
|---:|---:|---:|
| 1 | 440 | 75,779.72 |
| 2 | 398 | 63,737.85 |
| 3 | 417 | 70,347.71 |
| 4 | 408 | 62,938.08 |
| 5 | 420 | 67,710.08 |
| 6 | 379 | 63,468.38 |
| 7 | 427 | 66,266.28 |
| 8 | 426 | 64,914.03 |
| 9 | 398 | 65,416.97 |
| 10 | 438 | 73,885.87 |
| 11 | 407 | 64,532.19 |
| 12 | 442 | 72,999.28 |

**Interpretation:** Monthly transaction counts range from 379 (June) to 442 (December) and total value from roughly 62.9k to 75.8k BND. There is no pronounced seasonal peak, matching the near-uniform date sampling observed in Stage 3. The pipeline shows that date-part derivation and aggregation can be pushed into MongoDB rather than done in application code.

---

## 4. Reproduce

```powershell
cd "C:\Users\ASUS\Documents\Big Data Tech Task"
python digital_payment_analytics\mongodb_stage4.py
```

Requirements: a MongoDB server on `127.0.0.1:27017` (override with the `MONGO_URI` environment variable) and `pymongo` (`python -m pip install pymongo`). The script prints collection counts, all query/pipeline outputs and writes `mongodb_outputs/query_results.txt`.

> **Note on causality:** as in Stage 3, every result above is descriptive. Several patterns (segment–channel preference, category value ranges, income scaling) were programmed into the Stage 2 generator; observing them here confirms the model, not a real-world causal relationship.
