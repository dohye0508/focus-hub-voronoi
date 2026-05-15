import pandas as pd
import glob

files = glob.glob("*.xlsx")
if files:
    df = pd.read_excel(files[0])
    print(f"File: {files[0]}")
    print("Columns:", df.columns.tolist())
    print("\nFirst 5 rows:")
    print(df.head())
else:
    print("No excel files found.")
