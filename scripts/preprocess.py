import pandas as pd
import glob
import os

def merge_academy_data():
    files = glob.glob("acaInstiList_20260515_*.xlsx")
    all_dfs = []
    
    for f in files:
        print(f"Reading {f}...")
        try:
            # Skip rows if needed. Based on columns.txt, it seems there are some header rows to skip or handle.
            # Row 0-3 seem to be sub-headers or empty.
            df = pd.read_excel(f)
            # Find where the data actually starts. Usually '순번' or '학원명' is the key.
            # Let's try to find the row that contains '학원명'
            for i, row in df.iterrows():
                if '학원명' in row.values:
                    df.columns = row
                    df = df.iloc[i+1:]
                    break
            
            # Keep only relevant columns if they exist
            cols_to_keep = ['학원명', '주소', '교습과정']
            available_cols = [c for c in cols_to_keep if c in df.columns]
            df = df[available_cols].dropna(subset=['학원명', '주소'])
            
            # Add region info from filename
            region = f.split('_')[-1].replace('.xlsx', '')
            df['지역'] = region
            
            all_dfs.append(df)
        except Exception as e:
            print(f"Error reading {f}: {e}")
            
    if all_dfs:
        merged_df = pd.concat(all_dfs, ignore_index=True)
        merged_df.to_csv("academies_merged.csv", index=False, encoding='utf-8-sig')
        print(f"Saved {len(merged_df)} academies to academies_merged.csv")
        return merged_df
    return None

if __name__ == "__main__":
    merge_academy_data()
