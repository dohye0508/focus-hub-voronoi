import pandas as pd
import glob
import sys

# Set encoding to utf-8 for stdout
import io
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding = 'utf-8')

files = glob.glob("*.xlsx")
if files:
    # Try reading the first file
    df = pd.read_excel(files[0])
    with open("scratch/columns.txt", "w", encoding="utf-8") as f:
        f.write(f"File: {files[0]}\n")
        f.write("Columns: " + ", ".join(df.columns.astype(str).tolist()) + "\n")
        f.write("\nFirst 10 rows:\n")
        f.write(df.head(10).to_string())
else:
    print("No excel files found.")
