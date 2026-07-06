"""
test_data_loader.py
Purpose: Automated tests to confirm data_loader.py works correctly.
"""

import sys
import os

# Allow this test file to find our src/ folder
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from data_loader import load_price_data


def test_load_sample_data():
    df = load_price_data("data/raw/sample_eurusd.csv")

    # Check the DataFrame is not empty
    assert len(df) > 0, "Loaded data should not be empty"

    # Check all required columns exist
    for col in ["timestamp", "open", "high", "low", "close", "volume"]:
        assert col in df.columns, f"Missing expected column: {col}"

    # Check data is sorted by timestamp
    assert df["timestamp"].is_monotonic_increasing, "Data should be sorted by timestamp"

    # Check there are no duplicate timestamps
    assert df["timestamp"].duplicated().sum() == 0, "There should be no duplicate timestamps"

    print("✅ All test_data_loader tests passed!")


if __name__ == "__main__":
    test_load_sample_data()