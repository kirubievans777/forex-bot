"""
test_setup.py
Purpose: Confirm that Python and core packages are installed correctly.
"""

def check_python():
    import sys
    print(f"✅ Python is working. Version: {sys.version}")

def check_pandas():
    try:
        import pandas as pd
        print(f"✅ pandas is installed. Version: {pd.__version__}")
    except ImportError:
        print("❌ pandas is NOT installed. Run: pip install pandas")

def check_numpy():
    try:
        import numpy as np
        print(f"✅ numpy is installed. Version: {np.__version__}")
    except ImportError:
        print("❌ numpy is NOT installed. Run: pip install numpy")

def check_matplotlib():
    try:
        import matplotlib
        print(f"✅ matplotlib is installed. Version: {matplotlib.__version__}")
    except ImportError:
        print("❌ matplotlib is NOT installed. Run: pip install matplotlib")

if __name__ == "__main__":
    print("Running setup checks...\n")
    check_python()
    check_pandas()
    check_numpy()
    check_matplotlib()
    print("\nSetup check complete.")