"""
Synthetic data generator for the Brunei Digital Payment Analytics project.
=========================================================================

Purpose
-------
Produces the Stage 2 "main" fact file (transactions.csv) and its supporting
dimension/lookup files (customers.csv, locations.csv, merchant_categories.csv,
payment_channels.csv). The script uses only the Python 3 standard library.

Design notes
------------
* The random number generator is seeded with 42, so every run reproduces the
  exact same five files. This is intentional: the dataset is fully synthetic
  and deterministic, which makes it safe to share and easy to regression-test.
* The generation rules are fixed and seeded, so every run recreates the
  same five CSVs from scratch without any external input files.
* No real customer, merchant or payment data is used. All names, IDs and
  values are fabricated.

Run from anywhere::

    python generate_synthetic_data.py

Outputs are written to ./data, inside ./digital_payment_analytics.
"""

import csv
import os
import random
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# 1. Configuration
# ---------------------------------------------------------------------------

SEED = 42
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(OUTPUT_DIR, exist_ok=True)

NUM_TRANSACTIONS = 5000
NUM_CUSTOMERS = 300
NUM_LOCATIONS = 100

CURRENCY = "BND"
COUNTRY = "Brunei Darussalam"
START_DATE = datetime(2025, 1, 1)
END_DATE = datetime(2025, 12, 31)

# ---------------------------------------------------------------------------
# 2. Reference / rule tables
# ---------------------------------------------------------------------------

# Segment -> demographic and behavioural rules.
SEGMENTS = {
    "Tech Savvy": {
        "age": (18, 30),
        "adoption": "High",
        "frequency": 0.95,
        "wallet": 0.45,
    },
    "Young Professionals": {
        "age": (25, 40),
        "adoption": "High",
        "frequency": 0.85,
        "wallet": 0.30,
    },
    "Working Adults": {
        "age": (35, 55),
        "adoption": "Medium",
        "frequency": 0.65,
        "wallet": 0.15,
    },
    "Traditional Users": {
        "age": (45, 65),
        "adoption": "Low",
        "frequency": 0.35,
        "wallet": 0.05,
    },
    "Senior Citizens": {
        "age": (60, 80),
        "adoption": "Low",
        "frequency": 0.20,
        "wallet": 0.02,
    },
}

SEGMENT_NAMES = list(SEGMENTS.keys())
SEGMENT_WEIGHTS = [25, 25, 25, 15, 10]

DISTRICTS = {
    "Brunei-Muara": [
        "Bandar Seri Begawan", "Gadong", "Kiulap", "Berakas",
        "Jerudong", "Rimba", "Muara", "Mentiri",
    ],
    "Belait": ["Kuala Belait", "Seria", "Lumut", "Sungai Liang"],
    "Tutong": ["Tutong Town", "Pekan Tutong", "Telisai", "Lamunin"],
    "Temburong": ["Bangar", "Batang Duri", "Amo", "Labu"],
}
DISTRICT_WEIGHTS = [60, 20, 12, 8]

# Merchant category -> plausible BND value range (min, max).
MERCHANT_CATEGORIES = {
    "Grocery": (5, 150),
    "Restaurant": (5, 100),
    "Retail": (10, 500),
    "Transportation": (2, 50),
    "Healthcare": (10, 300),
    "Entertainment": (5, 200),
    "Utilities": (20, 500),
    "Education": (10, 500),
    "Travel": (50, 1500),
    "Online Shopping": (10, 400),
}
CATEGORY_WEIGHTS = [18, 20, 16, 12, 5, 6, 8, 5, 3, 7]

CHANNEL_NAMES = [
    "Mobile Wallet",
    "QR Payment",
    "Debit Card",
    "Credit Card",
    "Online Banking",
    "Bank Transfer",
]

CHANNEL_WEIGHTS = {
    "Tech Savvy": [35, 30, 10, 5, 15, 5],
    "Young Professionals": [25, 25, 15, 10, 20, 5],
    "Working Adults": [15, 20, 20, 10, 25, 10],
    "Traditional Users": [5, 10, 30, 15, 25, 15],
    "Senior Citizens": [2, 5, 35, 10, 30, 18],
}

# (start_hour, end_hour_exclusive, relative_weight)
TIME_PERIODS = [
    (7, 10, 15),
    (10, 14, 25),
    (14, 17, 20),
    (17, 21, 30),
    (21, 23, 10),
]


# ---------------------------------------------------------------------------
# 3. Helper
# ---------------------------------------------------------------------------

def write_csv(filename, rows):
    """Write a list of ordered dictionaries to a CSV file; return the path."""
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


# ---------------------------------------------------------------------------
# 4. Dimension / lookup generators
# ---------------------------------------------------------------------------

def generate_customers(num_customers=NUM_CUSTOMERS):
    """Create the customer master table (one row per synthetic person)."""
    customers = []

    for i in range(1, num_customers + 1):
        segment = random.choices(SEGMENT_NAMES, weights=SEGMENT_WEIGHTS)[0]
        info = SEGMENTS[segment]
        age = random.randint(*info["age"])
        tenure = random.randint(1, 60 if info["adoption"] == "High" else 36)

        customers.append({
            "customer_id": f"C{i:04d}",
            "age": age,
            "gender": random.choice(["Male", "Female"]),
            "occupation": random.choice([
                "Student", "Private Sector", "Government",
                "Self Employed", "Retired", "Other",
            ]),
            "customer_segment": segment,
            "adoption_level": info["adoption"],
            "adoption_tenure_months": tenure,
            "monthly_income_bnd": random.choice([
                500, 1000, 1500, 2000, 2500, 3000, 4000, 5000, 6000,
            ]),
            "primary_payment_channel": random.choice([
                "Mobile Wallet", "QR Payment", "Debit Card", "Online Banking",
            ]),
            "digital_payment_frequency": random.choice([
                "Daily", "Weekly", "Monthly", "Occasional",
            ]),
        })

    return customers


def generate_locations(num_locations=NUM_LOCATIONS):
    """Create the location master table (one row per synthetic area)."""
    locations = []

    for i in range(1, num_locations + 1):
        district = random.choices(
            list(DISTRICTS.keys()), weights=DISTRICT_WEIGHTS
        )[0]
        area = random.choice(DISTRICTS[district])

        # Brunei-Muara is treated as wholly urban in this synthetic model.
        if district == "Brunei-Muara":
            urbanity = "Urban"
        else:
            urbanity = random.choice(["Urban", "Suburban", "Rural"])

        locations.append({
            "location_id": f"L{i:03d}",
            "district": district,
            "area_name": area,
            "urbanity": urbanity,
            "country": COUNTRY,
            "latitude": round(random.uniform(4.5, 5.1), 5),
            "longitude": round(random.uniform(114.5, 115.5), 5),
        })

    return locations


def generate_merchant_categories():
    """Create the merchant-category lookup from the rule table above."""
    rows = []

    for category, (minimum, maximum) in MERCHANT_CATEGORIES.items():
        rows.append({
            "merchant_category": category,
            "typical_min_value_bnd": minimum,
            "typical_max_value_bnd": maximum,
            "selection_weight": CATEGORY_WEIGHTS[
                list(MERCHANT_CATEGORIES.keys()).index(category)
            ],
        })

    return rows


def generate_payment_channels():
    """Create the payment-channel lookup from the rule table above."""
    descriptions = {
        "Mobile Wallet": "Wallet balance or linked-account mobile payment",
        "QR Payment": "Scan-and-pay QR code settlement",
        "Debit Card": "Card payment debited directly from bank account",
        "Credit Card": "Card payment settled on a credit line",
        "Online Banking": "Internet or mobile banking transfer/payment",
        "Bank Transfer": "Account-to-account transfer (e.g. FAST/PayNow style)",
    }

    return [
        {
            "payment_channel": name,
            "channel_id": f"PC{index:02d}",
            "channel_description": descriptions[name],
        }
        for index, name in enumerate(CHANNEL_NAMES, start=1)
    ]


# ---------------------------------------------------------------------------
# 5. Main fact table generator
# ---------------------------------------------------------------------------

def generate_transactions(customers, locations, num_transactions=NUM_TRANSACTIONS):
    """Create the transaction fact table (one row per synthetic payment)."""
    category_names = list(MERCHANT_CATEGORIES.keys())
    transactions = []

    for i in range(1, num_transactions + 1):
        customer = random.choice(customers)
        segment = customer["customer_segment"]
        frequency = SEGMENTS[segment]["frequency"]

        # Urban locations are sampled more heavily than suburban/rural ones.
        location = random.choices(
            locations,
            weights=[
                3 if place["urbanity"] == "Urban"
                else 2 if place["urbanity"] == "Suburban"
                else 1
                for place in locations
            ],
        )[0]

        random_days = random.randint(
            0, (END_DATE - START_DATE).days
        )
        transaction_date = START_DATE + timedelta(days=random_days)

        period = random.choices(
            TIME_PERIODS, weights=[slot[2] for slot in TIME_PERIODS]
        )[0]
        hour = random.randint(period[0], period[1] - 1)
        minute = random.randint(0, 59)
        transaction_datetime = transaction_date.replace(
            hour=hour,
            minute=minute,
            second=random.randint(0, 59),
        )

        category = random.choices(
            category_names, weights=CATEGORY_WEIGHTS
        )[0]
        minimum, maximum = MERCHANT_CATEGORIES[category]
        transaction_value = round(random.uniform(minimum, maximum), 2)

        # Higher-income customers spend slightly more within the same range.
        income_factor = customer["monthly_income_bnd"] / 2500
        transaction_value = round(
            transaction_value * (0.8 + income_factor * 0.2), 2
        )

        channel = random.choices(
            CHANNEL_NAMES, weights=CHANNEL_WEIGHTS[segment]
        )[0]

        # Less digitally adopted users sometimes fall back to traditional rails.
        if random.random() > frequency:
            channel = random.choice([
                "Debit Card", "Credit Card", "Bank Transfer",
            ])

        # Urban locations give wallet/QR a small extra boost.
        if location["urbanity"] == "Urban":
            if random.random() < 0.15:
                channel = random.choice(["Mobile Wallet", "QR Payment"])

        status = random.choices(
            ["Successful", "Failed", "Pending"], weights=[94, 4, 2]
        )[0]

        if channel in ["Mobile Wallet", "QR Payment"]:
            device = "Smartphone"
        elif channel == "Online Banking":
            device = random.choice(["Smartphone", "Computer"])
        else:
            device = random.choice([
                "Smartphone", "Computer", "POS Terminal",
            ])

        cross_border = random.choices(["Yes", "No"], weights=[5, 95])[0]

        transactions.append({
            "transaction_id": f"T{i:06d}",
            "customer_id": customer["customer_id"],
            "transaction_datetime": transaction_datetime.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "transaction_date": transaction_datetime.strftime("%Y-%m-%d"),
            "transaction_hour": hour,
            "day_of_week": transaction_datetime.strftime("%A"),
            "transaction_value_bnd": transaction_value,
            "payment_channel": channel,
            "merchant_category": category,
            "location_id": location["location_id"],
            "transaction_status": status,
            "device_type": device,
            # Deliberate denormalisation for analyst convenience.
            "customer_segment": segment,
            "adoption_level": customer["adoption_level"],
            "adoption_tenure_months": customer["adoption_tenure_months"],
            "is_cross_border": cross_border,
            "currency": CURRENCY,
        })

    return transactions


# ---------------------------------------------------------------------------
# 6. Entry point
# ---------------------------------------------------------------------------

def main():
    random.seed(SEED)

    customers = generate_customers()
    locations = generate_locations()
    categories = generate_merchant_categories()
    channels = generate_payment_channels()
    transactions = generate_transactions(customers, locations)

    written_files = [
        ("transactions.csv (main)", write_csv("transactions.csv", transactions)),
        ("customers.csv", write_csv("customers.csv", customers)),
        ("locations.csv", write_csv("locations.csv", locations)),
        ("merchant_categories.csv", write_csv("merchant_categories.csv", categories)),
        ("payment_channels.csv", write_csv("payment_channels.csv", channels)),
    ]

    print("=" * 46)
    print("STAGE 2 SYNTHETIC DATA GENERATION COMPLETE")
    print("=" * 46)
    print(f"Random seed: {SEED} (fully reproducible)\n")

    for label, path in written_files:
        with open(path, newline="", encoding="utf-8") as handle:
            row_count = sum(1 for _ in handle) - 1
        print(f"{label:<28} {row_count:>6,} rows  ->  {path}")

    print("\nAll files written successfully.")


if __name__ == "__main__":
    main()
