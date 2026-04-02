"""Simulate load_all_tours to find what's being filtered out."""
import glob, csv, json, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

settings = json.load(open(r'config\defaults\iconic\settings.json','r',encoding='utf-8'))
enabled = set(settings.get('enabled_tours',[]))
if enabled == "__ALL__":
    enabled_all = True
else:
    enabled_all = False
print(f'Enabled tours: {len(enabled)}')

# Load tour_company_assignments
assignments = {}
if os.path.exists('config/tour_company_assignments.json'):
    with open('config/tour_company_assignments.json','r',encoding='utf-8') as f:
        assignments = json.load(f)
print(f'Assignments: {len(assignments)}')

loaded_tour_keys = set()
loaded_tour_names_by_company = {}
included = 0
skipped_dup_key = 0
skipped_dup_name = 0
skipped_disabled = 0
dup_name_details = []

company_dirs = glob.glob('data/*/')
for cd in company_dirs:
    cn = os.path.basename(cd.rstrip('/\\'))
    csvs = glob.glob(f'{cd}en/*_with_media.csv')
    for cf in csvs:
        with open(cf, 'r', encoding='utf-8', newline='') as f:
            for row in csv.DictReader(f):
                tid = row['id']
                name = row['name']
                csv_company = row['company_name']
                key = f"{csv_company}__{tid}"
                company = assignments.get(key, csv_company)
                
                if key in loaded_tour_keys:
                    skipped_dup_key += 1
                    continue
                loaded_tour_keys.add(key)
                
                name_company_key = f"{company}::{name}"
                if name_company_key in loaded_tour_names_by_company:
                    skipped_dup_name += 1
                    dup_name_details.append(f"  {key} (name='{name[:40]}', company={company}) dup of {loaded_tour_names_by_company[name_company_key]}")
                    continue
                loaded_tour_names_by_company[name_company_key] = key
                
                if not enabled_all and key not in enabled:
                    skipped_disabled += 1
                    continue
                
                included += 1

print(f'\nResults:')
print(f'  Included: {included}')
print(f'  Skipped (dup key): {skipped_dup_key}')
print(f'  Skipped (dup name): {skipped_dup_name}')
print(f'  Skipped (disabled): {skipped_disabled}')
if dup_name_details:
    print(f'\nDuplicate name details:')
    for d in dup_name_details:
        print(d)
