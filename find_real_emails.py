import csv
import glob
import re

# Extract emails from CSV raw_text fields
emails_found = {}

for csv_file in glob.glob('tours_*_cleaned.csv'):
    company_name = csv_file.replace('tours_', '').replace('_cleaned.csv', '')
    
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                # Check raw_text field for emails
                raw_text = row.get('raw_text', '')
                
                # Find all email addresses in the raw text
                email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
                found_emails = re.findall(email_pattern, raw_text)
                
                # Filter out common noise/test emails
                real_emails = [e for e in found_emails if not any(x in e.lower() for x in ['example.com', 'test', 'schema.org', '@2x'])]
                
                if real_emails and company_name not in emails_found:
                    emails_found[company_name] = list(set(real_emails))  # Remove duplicates
                    break  # Only need first occurrence
                    
    except Exception as e:
        print(f"Error reading {csv_file}: {e}")

# Also check the raw (non-cleaned) CSVs
for csv_file in glob.glob('tours_*.csv'):
    if '_cleaned' in csv_file:
        continue
        
    company_name = csv_file.replace('tours_', '').replace('.csv', '')
    
    if company_name in emails_found:
        continue  # Already found
    
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
            # Find all email addresses
            email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
            found_emails = re.findall(email_pattern, content)
            
            # Filter out noise
            real_emails = [e for e in found_emails if not any(x in e.lower() for x in ['example.com', 'test', 'schema.org', '@2x'])]
            
            if real_emails:
                emails_found[company_name] = list(set(real_emails))
                
    except Exception as e:
        print(f"Error reading {csv_file}: {e}")

print("\n" + "="*80)
print("ACTUAL EMAIL ADDRESSES FOUND IN SCRAPED DATA")
print("="*80 + "\n")

if emails_found:
    for company in sorted(emails_found.keys()):
        print(f"Company: {company}")
        for email in emails_found[company]:
            print(f"  - {email}")
        print()
else:
    print("No email addresses found in CSV data.")

print(f"\nTotal companies with emails found: {len(emails_found)}")
print("="*80)

















