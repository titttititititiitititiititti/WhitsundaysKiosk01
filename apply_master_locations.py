#!/usr/bin/env python3
"""
Read the MASTER_LOCATIONS_LIST.txt and apply locations to all CSVs.
Extracts coordinates from brackets and saves them for the map.
"""

import csv
import glob
import re
import json

def parse_location_with_coords(location_text):
    """
    Parse location text and extract coordinates if present.
    Format: "Location Name" (lat, lng) or Location Name (-20.123, 148.456)
    Returns: (location_name, lat, lng) or (location_name, None, None)
    """
    # Try to find coordinates in parentheses
    coord_match = re.search(r'\((-?\d+\.?\d*),\s*(-?\d+\.?\d*)\)', location_text)
    
    if coord_match:
        lat = float(coord_match.group(1))
        lng = float(coord_match.group(2))
        # Remove the coordinate part to get clean location name
        location_name = re.sub(r'\s*\((-?\d+\.?\d*),\s*(-?\d+\.?\d*)\)\s*', '', location_text)
        location_name = location_name.strip().strip('"').strip()
        return location_name, lat, lng
    else:
        # No coordinates found, just return the location name
        location_name = location_text.strip().strip('"').strip()
        return location_name, None, None


def parse_master_list(filename):
    """Parse the master list file and return a dict of {company: {tour_id: location}}."""
    
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split by company sections
    company_sections = re.split(r'={80}\nCOMPANY: ', content)[1:]  # Skip header
    
    company_locations = {}
    all_coordinates = {}  # Store all location coordinates
    
    for section in company_sections:
        lines = section.split('\n')
        company_name = lines[0].strip()
        
        print(f"\n{company_name}:")
        
        # Find company default (can span multiple lines)
        company_default = None
        company_default_text = ""
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith('COMPANY DEFAULT DEPARTURE LOCATION:'):
                # Collect the default, might span multiple lines
                default_start = line.split(':', 1)[1].strip()
                if default_start and default_start != '_______________________________':
                    company_default_text = default_start
                    # Check if next line continues the location (for multiline entries)
                    j = i + 1
                    while j < len(lines) and not lines[j].startswith('Tours'):
                        next_line = lines[j].strip()
                        if next_line and not next_line.startswith('=') and not next_line.startswith('Total tours'):
                            company_default_text += ' ' + next_line
                        j += 1
                    
                    # Parse the location and coordinates
                    loc_name, lat, lng = parse_location_with_coords(company_default_text)
                    company_default = loc_name
                    
                    if lat and lng:
                        all_coordinates[loc_name] = {'lat': lat, 'lng': lng}
                        print(f"  Default: {loc_name} ({lat}, {lng})")
                    else:
                        print(f"  Default: {loc_name}")
                break
            i += 1
        
        # Parse tours
        tour_locations = {}
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Look for tour ID pattern: [tour_id] Tour Name
            tour_match = re.match(r'\s*\[([^\]]*)\]\s+(.+)', line)
            if tour_match:
                tour_id = tour_match.group(1).strip()
                tour_name = tour_match.group(2).strip()
                
                # Look ahead for location information
                tour_location = None
                tour_location_text = ""
                current_location_text = ""
                
                # Check next few lines for "Current:", "Location:", or "Override:"
                for j in range(i+1, min(i+10, len(lines))):
                    next_line = lines[j]
                    
                    # First priority: Override field
                    if 'Override:' in next_line:
                        location = next_line.split('Override:', 1)[1].strip()
                        if location and location != '_______________________________':
                            tour_location_text = location
                            k = j + 1
                            while k < len(lines) and not re.match(r'\s*\[[^\]]*\]', lines[k]) and not lines[k].strip().startswith('='):
                                continuation = lines[k].strip()
                                if continuation and not continuation.startswith('Current') and not continuation.startswith('Override') and not continuation.startswith('Location'):
                                    tour_location_text += ' ' + continuation
                                else:
                                    break
                                k += 1
                    
                    # Second priority: Current field (if Override is blank)
                    elif 'Current:' in next_line:
                        location = next_line.split('Current:', 1)[1].strip()
                        if location and location != '_______________________________':
                            current_location_text = location
                    
                    # Third priority: Location field
                    elif 'Location:' in next_line:
                        location = next_line.split('Location:', 1)[1].strip()
                        if location and location != '_______________________________':
                            if not tour_location_text and not current_location_text:
                                tour_location_text = location
                                k = j + 1
                                while k < len(lines) and not re.match(r'\s*\[[^\]]*\]', lines[k]) and not lines[k].strip().startswith('='):
                                    continuation = lines[k].strip()
                                    if continuation and not continuation.startswith('Current') and not continuation.startswith('Override') and not continuation.startswith('Location'):
                                        tour_location_text += ' ' + continuation
                                    else:
                                        break
                                    k += 1
                
                # Use Override if set, otherwise use Current
                if not tour_location_text and current_location_text:
                    tour_location_text = current_location_text
                
                # Parse location and extract coordinates
                if tour_location_text:
                    loc_name, lat, lng = parse_location_with_coords(tour_location_text)
                    tour_location = loc_name
                    if lat and lng:
                        all_coordinates[loc_name] = {'lat': lat, 'lng': lng}
                
                # Use tour-specific location, or fall back to company default
                final_location = tour_location if tour_location else company_default
                
                if final_location:
                    tour_locations[tour_id] = final_location
                    if tour_location:
                        coords_str = f"({all_coordinates[tour_location]['lat']}, {all_coordinates[tour_location]['lng']})" if tour_location in all_coordinates else ""
                        print(f"  ✓ [{tour_id[:8]}...] {tour_name[:35]} -> {tour_location[:40]} {coords_str}")
            
            i += 1
        
        if company_default and not tour_locations:
            print(f"  (Default will apply to all {len([l for l in lines if '[' in l and ']' in l])} tours)")
        elif company_default:
            default_count = sum(1 for loc in tour_locations.values() if loc == company_default)
            if default_count > 0:
                print(f"  Applied default to {default_count} tour(s)")
        
        company_locations[company_name] = {
            'default': company_default,
            'tours': tour_locations
        }
    
    return company_locations, all_coordinates


def apply_locations_to_csvs(company_locations):
    """Apply the locations to all CSV files."""
    
    print("\n" + "="*80)
    print("UPDATING CSV FILES")
    print("="*80)
    
    total_updated = 0
    
    for company_name, data in company_locations.items():
        csv_file = f'tours_{company_name}_cleaned_with_media.csv'
        
        try:
            # Read the CSV
            with open(csv_file, 'r', encoding='utf-8', newline='') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                fieldnames = reader.fieldnames
            
            # Update departure_location field
            updated = 0
            for row in rows:
                tour_id = row.get('tour_id', '').strip()
                
                # Check if we have a location for this tour
                if tour_id in data['tours']:
                    row['departure_location'] = data['tours'][tour_id]
                    updated += 1
                elif data['default']:
                    # Use company default
                    row['departure_location'] = data['default']
                    updated += 1
            
            # Write back
            with open(csv_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            
            if updated > 0:
                print(f"  ✓ {company_name}: Updated {updated}/{len(rows)} tours")
            total_updated += updated
            
        except FileNotFoundError:
            print(f"  ⚠️  {company_name}: CSV file not found")
    
    print(f"\n  Total: {total_updated} tours updated")
    return total_updated


def update_javascript_coordinates(all_coordinates):
    """Update the LOCATION_COORDINATES in templates/index.html"""
    
    print("\n" + "="*80)
    print("UPDATING MAP COORDINATES")
    print("="*80)
    
    # Read the current index.html
    with open('templates/index.html', 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Build the new LOCATION_COORDINATES object
    js_coords = "        const LOCATION_COORDINATES = {\n"
    
    for location, coords in sorted(all_coordinates.items()):
        # Normalize location name for JS key (remove special chars, lowercase, spaces to underscores)
        js_key = location.lower().replace(' ', '_').replace(',', '').replace("'", '').replace('"', '').replace('/', '_').replace('(', '').replace(')', '')
        js_coords += f"            '{location}': {{ lat: {coords['lat']}, lng: {coords['lng']} }},\n"
    
    js_coords += "        };"
    
    # Replace the existing LOCATION_COORDINATES in the HTML
    pattern = r'const LOCATION_COORDINATES = \{[^}]*\};'
    if re.search(pattern, html_content, re.DOTALL):
        html_content = re.sub(pattern, js_coords.strip(), html_content, flags=re.DOTALL)
        
        # Write back
        with open('templates/index.html', 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"  ✓ Added {len(all_coordinates)} locations to map")
        print("\n  Locations added:")
        for location, coords in sorted(all_coordinates.items()):
            print(f"    • {location}")
    else:
        print("  ⚠️  Could not find LOCATION_COORDINATES in index.html")


def main():
    print("="*80)
    print("APPLYING MASTER LOCATIONS LIST")
    print("="*80)
    
    # Parse the master list
    company_locations, all_coordinates = parse_master_list('MASTER_LOCATIONS_LIST.txt')
    
    # Apply to CSVs
    total_updated = apply_locations_to_csvs(company_locations)
    
    # Update JavaScript coordinates if we have new ones
    if all_coordinates:
        update_javascript_coordinates(all_coordinates)
    
    print("\n" + "="*80)
    print(f"✅ COMPLETE!")
    print("="*80)
    print(f"  • {total_updated} tours updated")
    print(f"  • {len(all_coordinates)} locations with coordinates")
    print("\n  Refresh your browser to see the updated maps!")


if __name__ == '__main__':
    main()
