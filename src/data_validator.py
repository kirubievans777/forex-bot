"""
data_validator.py
Purpose: Run deeper quality checks on price data to catch issues
         that could break a backtest or produce misleading results.
"""

import pandas as pd

REQUIRED_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]


def validate_data(df):
    """
    Runs a series of checks on a price DataFrame and returns a report
    (a dictionary) describing any problems found.
    """

    report = {
        "missing_columns": [],
        "missing_values": {},
        "duplicate_timestamps": 0,
        "incorrect_price_rows": 0,
        "time_gaps": [],
    }

    # Check 1: Missing columns
    report["missing_columns"] = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if report["missing_columns"]:
        # If columns are missing, we can't safely run the other checks
        return report

    # Check 2: Missing values
    missing = df.isnull().sum()
    report["missing_values"] = {col: int(count) for col, count in missing.items() if count > 0}

    # Check 3: Duplicate timestamps
    report["duplicate_timestamps"] = int(df.duplicated(subset="timestamp").sum())

    # Check 4: Incorrect price values
    # A row is "incorrect" if high is not the highest value, or low is not the lowest,
    # or any price is zero/negative.
    incorrect_mask = (
        (df["high"] < df["low"]) |
        (df["high"] < df["open"]) |
        (df["high"] < df["close"]) |
        (df["low"] > df["open"]) |
        (df["low"] > df["close"]) |
        (df["open"] <= 0) |
        (df["high"] <= 0) |
        (df["low"] <= 0) |
        (df["close"] <= 0)
    )
    report["incorrect_price_rows"] = int(incorrect_mask.sum())

  # Check 5: Time gaps (only meaningful if data is sorted and has a consistent interval)
    if len(df) > 1:
        df_sorted = df.sort_values("timestamp").reset_index(drop=True)
        time_diffs = df_sorted["timestamp"].diff()
        if time_diffs.notna().sum() > 0:
            most_common_interval = time_diffs.mode()[0]
            gap_mask = time_diffs > most_common_interval
            gaps = df_sorted.loc[gap_mask, "timestamp"]
            report["time_gaps"] = gaps.astype(str).tolist()

    return report


def print_report(report):
    """Prints a validation report in a readable format."""
    print("\n--- Data Validation Report ---")

    if report["missing_columns"]:
        print(f"❌ Missing columns: {report['missing_columns']}")
        print("Cannot run further checks until columns are fixed.")
        return

    if report["missing_values"]:
        print(f"⚠️ Missing values found: {report['missing_values']}")
    else:
        print("✅ No missing values.")

    if report["duplicate_timestamps"] > 0:
        print(f"⚠️ Duplicate timestamps found: {report['duplicate_timestamps']}")
    else:
        print("✅ No duplicate timestamps.")

    if report["incorrect_price_rows"] > 0:
        print(f"❌ Rows with incorrect price logic: {report['incorrect_price_rows']}")
    else:
        print("✅ No incorrect price rows detected.")

    if report["time_gaps"]:
        print(f"⚠️ Time gaps detected at: {report['time_gaps']}")
    else:
        print("✅ No unexpected time gaps detected.")

    print("--- End of Report ---\n")


if __name__ == "__main__":
    from data_loader import load_price_data

    sample_path = "data/raw/sample_eurusd.csv"
    data = load_price_data(sample_path)
    result = validate_data(data)
    print_report(result)