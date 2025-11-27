import csv
import os
import shutil

# Helper to clear the screen (works on Windows and Unix)
def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def prompt_filename():
    while True:
        fname = input('Enter the CSV filename (e.g., tours_truebluesailing_cleaned.csv): ').strip()
        if os.path.isfile(fname):
            return fname
        print('File not found. Try again.')

def backup_csv(fname):
    backup = fname + '.bak'
    shutil.copy(fname, backup)
    print(f'Backup saved as {backup}')

def load_csv(fname):
    with open(fname, newline='', encoding='utf-8') as f:
        reader = list(csv.DictReader(f))
        fieldnames = reader[0].keys() if reader else []
        return reader, list(fieldnames)

def save_csv(fname, fieldnames, rows):
    with open(fname, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f'Saved changes to {fname}')

def edit_tour(tour, fieldnames):
    while True:
        print('\nCurrent tour fields:')
        for i, field in enumerate(fieldnames):
            print(f'  {i+1}. {field}: {tour.get(field, "")}')
        choice = input("Enter the number of the field to edit (or 'q' to quit editing): ").strip()
        if choice.lower() == 'q':
            break
        if choice.isdigit() and 1 <= int(choice) <= len(fieldnames):
            field = fieldnames[int(choice)-1]
            new_val = input(f'Enter new value for {field} (leave blank to keep current): ').strip()
            if new_val != '':
                tour[field] = new_val
        else:
            print('Invalid choice. Try again.')

def main():
    clear_screen()
    print('--- Tour CSV Interactive Editor ---')
    fname = prompt_filename()
    backup_csv(fname)
    rows, fieldnames = load_csv(fname)
    i = 0
    while i < len(rows):
        clear_screen()
        tour = rows[i]
        print(f"\nTour {i+1} of {len(rows)}:")
        print(f"  Name: {tour.get('name', '')}")
        print(f"  Description: {tour.get('description', '')[:100]}{'...' if len(tour.get('description',''))>100 else ''}")
        print(f"  Price (Adult): {tour.get('price_adult', '')}")
        print(f"  Price (Child): {tour.get('price_child', '')}")
        print(f"  Duration: {tour.get('duration', '')}")
        print(f"  [n] Next  [e] Edit  [delete] Delete  [q] Quit and Save")
        cmd = input('> ').strip().lower()
        if cmd == 'n':
            i += 1
        elif cmd == 'e':
            edit_tour(tour, fieldnames)
        elif cmd == 'delete':
            confirm = input('Are you sure you want to delete this tour? (y/n): ').strip().lower()
            if confirm == 'y':
                del rows[i]
                print('Tour deleted.')
                # Don't increment i, stay at current index
            else:
                print('Delete cancelled.')
        elif cmd == 'q':
            break
        else:
            print('Invalid command. Try again.')
    save_csv(fname, fieldnames, rows)
    print('Done!')

if __name__ == '__main__':
    main() 