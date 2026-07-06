"""
convert_dukascopy.py
Purpose: Convert a raw Dukascopy CSV export into our standard format
         (timestamp, open, high, low, close, volume), and optionally
         resample finer data (e.g. 1-minute) into a chosen timeframe
         (e.g. 1-hour) to reduce noise.
"""

import pandas as pd
import os

RAW_PATH = "data/raw/eurusd_h4_dukascopy.csv"     # your downloaded file
PROCESSED_PATH = "data/processed/eurusd_h4.csv"   # cleaned output
RESAMPLE_TO = None  # This data is already H4 — no resampling needed


def convert_dukascopy_csv(raw_path, processed_path, resample_to=None):
    # Step 1: Load the raw Dukascopy file
    df = pd.read_csv(raw_path)

    # Step 2: Rename columns to our standard names
    df = df.rename(columns={
        "Etc/UTC": "timestamp",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
    })

    # Step 3: Convert timestamp text into real datetime objects
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Step 4: Sort chronologically, just in case
    df = df.sort_values("timestamp")

    # Step 5 (optional): Resample into a larger timeframe (e.g. 1-hour candles)
    if resample_to:
        df = df.set_index("timestamp")
        df = df.resample(resample_to).agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        })
        # Resampling can create empty rows if there's a gap with no trades — drop those
        df = df.dropna()
        df = df.reset_index()

    # Step 6: Save to the processed folder
    os.makedirs(os.path.dirname(processed_path), exist_ok=True)
    df.to_csv(processed_path, index=False)

    print(f"✅ Converted {len(df)} rows.")
    print(f"Saved to: {processed_path}")
    print("\nPreview:")
    print(df.head())


if __name__ == "__main__":
    convert_dukascopy_csv(RAW_PATH, PROCESSED_PATH, resample_to=RESAMPLE_TO)