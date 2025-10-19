"""
Merge cleaned CSV data into _with_media.csv files
Preserves image paths while updating tour details (prices, duration, etc.)
"""
import pandas as pd
import glob
import os

def merge_cleaned_to_media():
    """Find all _cleaned.csv files and merge them into corresponding _with_media.csv"""
    
    cleaned_files = glob.glob('*_cleaned.csv')
    
    if not cleaned_files:
        print("No _cleaned.csv files found to merge.")
        return
    
    print(f"Found {len(cleaned_files)} cleaned CSV files to merge:\n")
    
    for cleaned_file in cleaned_files:
        # Derive the corresponding _with_media.csv filename
        base_name = cleaned_file.replace('_cleaned.csv', '')
        media_file = f"{base_name}_cleaned_with_media.csv"
        
        # Check if _with_media.csv exists
        if not os.path.exists(media_file):
            print(f"[SKIP] {cleaned_file}")
            print(f"       {media_file} does not exist")
            print()
            continue
        
        try:
            # Load both CSVs
            df_cleaned = pd.read_csv(cleaned_file)
            df_media = pd.read_csv(media_file)
            
            print(f"[OK] {cleaned_file}")
            print(f"     Merging into {media_file}")
            
            # Merge on 'id' column (keep all rows from media, update with cleaned data)
            # This preserves image_url and image_urls from media file
            
            # Get columns that should be updated from cleaned (exclude image columns)
            update_cols = [col for col in df_cleaned.columns 
                          if col not in ['image_url', 'image_urls'] and col in df_media.columns]
            
            # Check if IDs match between files - if not, try matching by URL
            if 'id' not in df_cleaned.columns or 'id' not in df_media.columns:
                print(f"     [WARNING] 'id' column missing, skipping...")
                continue
            
            # Try to match by ID first
            # Filter out NaN IDs
            cleaned_ids = set(df_cleaned['id'].dropna().values)
            media_ids = set(df_media['id'].dropna().values)
            common_ids = cleaned_ids & media_ids
            
            if len(common_ids) == 0 or len(cleaned_ids) == 0 or len(media_ids) == 0:
                # IDs don't match - try matching by URL instead
                print(f"     [INFO] ID mismatch (old vs new IDs), matching by URL...")
                
                # Create URL to cleaned data mapping (handle duplicates by keeping first)
                url_to_cleaned = {}
                for _, row in df_cleaned.iterrows():
                    url = row.get('link_booking', '')
                    if url and url not in url_to_cleaned:
                        url_to_cleaned[url] = row.to_dict()
                
                updated_count = 0
                for idx, row in df_media.iterrows():
                    url = row.get('link_booking', '')
                    if url in url_to_cleaned:
                        cleaned_data = url_to_cleaned[url]
                        for col in update_cols:
                            if col in cleaned_data:
                                df_media.at[idx, col] = cleaned_data[col]
                        # Also update the ID to the new hash-based ID
                        df_media.at[idx, 'id'] = cleaned_data['id']
                        updated_count += 1
            else:
                # IDs match - use ID-based merging
                try:
                    # Remove any rows with duplicate IDs before set_index
                    df_cleaned_dedup = df_cleaned.drop_duplicates(subset=['id'], keep='first')
                    id_to_cleaned = df_cleaned_dedup.set_index('id')[update_cols].to_dict('index')
                    
                    updated_count = 0
                    for idx, row in df_media.iterrows():
                        tour_id = row['id']
                        if pd.notna(tour_id) and tour_id in id_to_cleaned:
                            for col in update_cols:
                                if col in id_to_cleaned[tour_id]:
                                    df_media.at[idx, col] = id_to_cleaned[tour_id][col]
                            updated_count += 1
                except Exception as e:
                    print(f"     [WARNING] ID-based merge failed: {e}")
                    print(f"     [INFO] Falling back to URL matching...")
                    # Fallback to URL matching
                    url_to_cleaned = {}
                    for _, row in df_cleaned.iterrows():
                        url = row.get('link_booking', '')
                        if url and url not in url_to_cleaned:
                            url_to_cleaned[url] = row.to_dict()
                    
                    updated_count = 0
                    for idx, row in df_media.iterrows():
                        url = row.get('link_booking', '')
                        if url in url_to_cleaned:
                            cleaned_data = url_to_cleaned[url]
                            for col in update_cols:
                                if col in cleaned_data:
                                    df_media.at[idx, col] = cleaned_data[col]
                            # Also update the ID to the new hash-based ID
                            if 'id' in cleaned_data:
                                df_media.at[idx, 'id'] = cleaned_data['id']
                            updated_count += 1
            
            # Save updated media file
            df_media.to_csv(media_file, index=False)
            print(f"     Updated {updated_count} tours")
            print(f"     Preserved image paths for all tours")
            print()
            
        except Exception as e:
            print(f"[ERROR] {cleaned_file}: {e}")
            print()
    
    print("=" * 60)
    print("Merge complete!")
    print("\nYour _with_media.csv files now have:")
    print("  [OK] Updated prices, durations, descriptions from latest scrape")
    print("  [OK] Original image paths preserved")

if __name__ == '__main__':
    merge_cleaned_to_media()

