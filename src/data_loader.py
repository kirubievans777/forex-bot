"""
data_loader.py
Purpose: Load a historical price CSV file, clean it, and return a
         ready-to-use pandas DataFrame.
"""

import pandas as pd

REQUIRED_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]


def load_price_data(filepath):
    """
    Loads a CSV file of OHLC price data and returns a cleaned DataFrame.

    Steps:
    1. Load the CSV
    2. Check required columns exist
    3. Convert timestamp to real datetime objects
    4. Sort by timestamp
    5. Remove duplicate timestamps
    6. Check for missing values
    """

    # Step 1: Load the CSV file into a DataFrame (a table-like structure)
    df = pd.read_csv(filepath)

    # Step 2: Validate required columns exist
    missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    # Step 3: Convert the timestamp column from plain text to real datetime objects
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Step 4: Sort rows chronologically (oldest to newest)
    df = df.sort_values("timestamp")

    # Step 5: Remove duplicate timestamps, keeping the first occurrence
    before_count = len(df)
    df = df.drop_duplicates(subset="timestamp", keep="first")
    duplicates_removed = before_count - len(df)
    if duplicates_removed > 0:
        print(f"⚠️ Removed {duplicates_removed} duplicate timestamp rows.")

    # Step 6: Check for missing values
    missing_values = df.isnull().sum()
    if missing_values.sum() > 0:
        print("⚠️ Missing values detected:")
        print(missing_values[missing_values > 0])
    else:
        print("✅ No missing values detected.")

    # Reset the row index so it's clean (0, 1, 2, ...) after sorting/deduplication
    df = df.reset_index(drop=True)

    return df


if __name__ == "__main__":
    # Quick manual test when running this file directly
    sample_path = "data/raw/sample_eurusd.csv"
    data = load_price_data(sample_path)
    print("\nLoaded data preview:")
    print(data.head())