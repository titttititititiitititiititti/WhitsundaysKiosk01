"""
Tour RAG Indexer - Creates semantic embeddings for all tours
Uses OpenAI embeddings + ChromaDB for local vector storage

Run this script whenever tours are updated to rebuild the index.
"""

import os
import sys
import csv
import glob
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

import openai
import chromadb
from chromadb.config import Settings

# Configuration
EMBEDDING_MODEL = "text-embedding-3-small"  # Fast and cheap: $0.00002/1K tokens
CHROMA_DB_PATH = "data/tour_embeddings"
COLLECTION_NAME = "tours"

def get_openai_client():
    """Get OpenAI client with API key"""
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in environment")
    return openai.OpenAI(api_key=api_key)

def load_all_tours():
    """Load all tours from CSV files"""
    tours = []
    data_dir = Path(__file__).parent.parent / "data"
    
    # Find all English tour CSVs
    csv_pattern = str(data_dir / "*" / "en" / "*.csv")
    csv_files = glob.glob(csv_pattern)
    
    print(f"Found {len(csv_files)} CSV files")
    
    for csv_file in csv_files:
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Skip inactive tours
                    if row.get('active', '').lower() == 'false':
                        continue
                    
                    # Extract company from path
                    company = Path(csv_file).parent.parent.name
                    
                    # Create unique key
                    tour_id = row.get('id', '')
                    key = f"{company}__{tour_id}"
                    
                    tour = {
                        'key': key,
                        'id': tour_id,
                        'name': row.get('name', ''),
                        'company': company,
                        'company_name': row.get('company_name', company),
                        'summary': row.get('summary', ''),
                        'description': row.get('description', ''),
                        'highlights': row.get('highlights', ''),
                        'includes': row.get('includes', ''),
                        'duration': row.get('duration', ''),
                        'duration_category': row.get('duration_category', ''),
                        'price_adult': row.get('price_adult', ''),
                        'ideal_for': row.get('ideal_for', ''),
                        'tags': row.get('tags', ''),
                        'keywords': row.get('keywords', ''),
                        'locations': row.get('locations', ''),
                        'audience': row.get('audience', ''),
                        'tour_type': row.get('tour_type', ''),
                        'promotion': row.get('promotion', ''),
                    }
                    tours.append(tour)
        except Exception as e:
            print(f"  Error reading {csv_file}: {e}")
    
    print(f"Loaded {len(tours)} tours total")
    return tours

def create_tour_text(tour):
    """Create a rich text representation of a tour for embedding"""
    parts = []
    
    # Name is most important
    if tour.get('name'):
        parts.append(f"Tour: {tour['name']}")
    
    # Company for brand recognition
    if tour.get('company_name'):
        parts.append(f"Operator: {tour['company_name']}")
    
    # Duration is a key filter
    if tour.get('duration'):
        parts.append(f"Duration: {tour['duration']}")
    if tour.get('duration_category'):
        parts.append(f"Type: {tour['duration_category'].replace('_', ' ')}")
    
    # Price for budget matching
    if tour.get('price_adult'):
        parts.append(f"Price: {tour['price_adult']}")
    
    # Description captures the experience
    if tour.get('description'):
        # Truncate long descriptions
        desc = tour['description'][:500]
        parts.append(f"Description: {desc}")
    
    # Highlights are key selling points
    if tour.get('highlights'):
        parts.append(f"Highlights: {tour['highlights'][:300]}")
    
    # What's included
    if tour.get('includes'):
        parts.append(f"Includes: {tour['includes'][:200]}")
    
    # Target audience
    if tour.get('ideal_for'):
        parts.append(f"Ideal for: {tour['ideal_for']}")
    if tour.get('audience'):
        parts.append(f"Audience: {tour['audience']}")
    
    # Keywords and tags for matching
    if tour.get('keywords'):
        parts.append(f"Keywords: {tour['keywords']}")
    if tour.get('tags'):
        parts.append(f"Tags: {tour['tags']}")
    
    # Locations
    if tour.get('locations'):
        parts.append(f"Locations: {tour['locations']}")
    
    # Tour type
    if tour.get('tour_type'):
        parts.append(f"Type: {tour['tour_type']}")
    
    return "\n".join(parts)

def create_embeddings(client, texts, batch_size=100):
    """Create embeddings for a list of texts in batches"""
    all_embeddings = []
    
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        print(f"  Embedding batch {i//batch_size + 1}/{(len(texts) + batch_size - 1)//batch_size}...")
        
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=batch
        )
        
        # Extract embeddings in order
        batch_embeddings = [item.embedding for item in response.data]
        all_embeddings.extend(batch_embeddings)
    
    return all_embeddings

def index_tours():
    """Main function to index all tours"""
    print("=" * 60)
    print("TOUR RAG INDEXER")
    print("=" * 60)
    
    # Load tours
    print("\n1. Loading tours from CSV files...")
    tours = load_all_tours()
    
    if not tours:
        print("No tours found! Check data directory.")
        return
    
    # Create text representations
    print("\n2. Creating text representations...")
    tour_texts = []
    tour_ids = []
    tour_metadata = []
    
    seen_keys = set()
    for tour in tours:
        # Skip duplicates (same tour from different language files)
        if tour['key'] in seen_keys:
            continue
        seen_keys.add(tour['key'])
        
        text = create_tour_text(tour)
        tour_texts.append(text)
        tour_ids.append(tour['key'])
        
        # Store metadata for retrieval
        metadata = {
            'name': tour.get('name', '')[:200],
            'company': tour.get('company', ''),
            'company_name': tour.get('company_name', '')[:100],
            'duration_category': tour.get('duration_category', ''),
            'price_adult': tour.get('price_adult', ''),
            'ideal_for': tour.get('ideal_for', '')[:200],
            'promotion': tour.get('promotion', ''),
            'tour_type': tour.get('tour_type', ''),
        }
        tour_metadata.append(metadata)
    
    print(f"   {len(tour_ids)} unique tours (filtered {len(tours) - len(tour_ids)} duplicates)")
    
    # Create embeddings
    print("\n3. Creating embeddings with OpenAI...")
    client = get_openai_client()
    embeddings = create_embeddings(client, tour_texts)
    
    print(f"   Created {len(embeddings)} embeddings")
    
    # Initialize ChromaDB
    print("\n4. Storing in ChromaDB...")
    db_path = Path(__file__).parent.parent / CHROMA_DB_PATH
    db_path.mkdir(parents=True, exist_ok=True)
    
    # Create persistent client
    chroma_client = chromadb.PersistentClient(path=str(db_path))
    
    # Delete existing collection if it exists
    try:
        chroma_client.delete_collection(COLLECTION_NAME)
        print("   Deleted existing collection")
    except:
        pass
    
    # Create new collection
    collection = chroma_client.create_collection(
        name=COLLECTION_NAME,
        metadata={"description": "Tour embeddings for semantic search"}
    )
    
    # Add documents in batches
    batch_size = 100
    for i in range(0, len(tour_ids), batch_size):
        end_idx = min(i + batch_size, len(tour_ids))
        collection.add(
            ids=tour_ids[i:end_idx],
            embeddings=embeddings[i:end_idx],
            metadatas=tour_metadata[i:end_idx],
            documents=tour_texts[i:end_idx]
        )
        print(f"   Added {end_idx}/{len(tour_ids)} tours to collection")
    
    print("\n" + "=" * 60)
    print(f"SUCCESS! Indexed {len(tours)} tours")
    print(f"Database location: {db_path}")
    print("=" * 60)
    
    # Quick test - use OpenAI embeddings for query too
    print("\n5. Quick test search: 'family snorkeling adventure'")
    test_query = "family snorkeling adventure on the reef"
    query_response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=[test_query]
    )
    query_embedding = query_response.data[0].embedding
    
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=3
    )
    
    print("\nTop 3 results:")
    for i, (id, metadata, distance) in enumerate(zip(
        results['ids'][0], 
        results['metadatas'][0],
        results['distances'][0]
    )):
        similarity = 1 - distance  # Convert distance to similarity
        print(f"  {i+1}. {metadata['name'][:50]}")
        print(f"     Company: {metadata['company_name']}")
        print(f"     Similarity: {similarity:.1%}")
        print()

if __name__ == "__main__":
    index_tours()

