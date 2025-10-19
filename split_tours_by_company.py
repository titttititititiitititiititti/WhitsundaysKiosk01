import pandas as pd
import os
import re

def safe_filename(name):
    return re.sub(r'[^a-zA-Z0-9_\-]', '_', name)

def split_tours_by_company(input_csv='tours_custom.csv'):
    df = pd.read_csv(input_csv)
    if 'company_name' not in df.columns:
        print("No 'company_name' column found in the CSV.")
        return
    grouped = df.groupby('company_name')
    for company, group in grouped:
        if not company or pd.isna(company):
            company = 'unknown'
        filename = f"tours_{safe_filename(company.lower())}.csv"
        group.to_csv(filename, index=False)
        print(f"Saved {len(group)} tours to {filename}")

if __name__ == '__main__':
    split_tours_by_company() 