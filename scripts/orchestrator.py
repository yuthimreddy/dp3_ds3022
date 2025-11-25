from prefect import flow, task
from alerce.core import Alerce # Importing Alerce to access the API for supernova data
import duckdb
import pandas as pd
import time
from datetime import datetime
import os

# Initializing Alerce client:
client = Alerce()
DB_NAME = "universe.duckdb" # Local DuckDB database file
TARGET_RECORDS = 100000 # Setting data record target


# == TASKS ==
# 1) Initializing DuckDB Database:
@task(name="Initialize Database")
def init_db():
    """Creates the table with proper constraints."""
    con = duckdb.connect(DB_NAME)
    con.execute("""
        CREATE TABLE IF NOT EXISTS supernovae (
            oid VARCHAR, 
            mjd DOUBLE, 
            magpsf DOUBLE, 
            fid INTEGER, 
            sigmapsf DOUBLE,
            ra DOUBLE,
            dec DOUBLE,
            inserted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (oid, mjd, fid)  -- Prevent duplicates
        )
    """)
    
    # Track processed candidates to avoid re-fetching
    con.execute("""
        CREATE TABLE IF NOT EXISTS processed_candidates (
            oid VARCHAR PRIMARY KEY,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    count = con.execute("SELECT COUNT(*) FROM supernovae").fetchone()[0]
    processed = con.execute("SELECT COUNT(*) FROM processed_candidates").fetchone()[0]
    con.close()
    
    # printing initialization results:
    print("Database initialized successfully.")
    print(f"Current record count: {count:,}, Processed candidates: {processed:,}")
    
    return count, processed

# 2) Getting already processed OIDs: OIDs are unique object identifiers for supernovae
@task(name="Get Processed OIDs")
def get_processed_oids():
    """Returns set of already-processed candidate IDs."""
    con = duckdb.connect(DB_NAME)
    # Querying db for all OIDs we have processed:
    result = con.execute("SELECT oid FROM processed_candidates").fetchall()
    con.close()
    oid_set = set(row[0] for row in result)
    print(f"Loaded {len(oid_set):,} previously processed OIDs")
    return oid_set

@task(name="Fetch Batch")
def fetch_batch(page_number, processed_oids):
    """Fetches one page of Supernovae and their light curves."""
    print(f"Fetching page {page_number}...")
    
    try:
        # Get Candidates with better filters
        candidates = client.query_objects(
            classifier="stamp_classifier", 
            class_name="SN", 
            probability=0.7,  # Higher quality: means AI is 70% confident in identification
            page_size=50,     # larger batch size for quicker fetches
            page=page_number,
            firstmjd=60000,   # Recent events only (~2023+)
            format="pandas"
        )
        
        if candidates.empty:
            print(f"Page {page_number}: No candidates returned")
            return pd.DataFrame(), []
        
        # Filter out already processed
        new_candidates = candidates[~candidates['oid'].isin(processed_oids)]
        
        if new_candidates.empty:
            print(f"Page {page_number}: All candidates already processed")
            return pd.DataFrame(), []
        
        print(f"Page {page_number}: Found {len(new_candidates)} new candidates")
        
        # Get Detections
        batch_detections = []
        processed_oids_batch = []
        
        for idx, row in new_candidates.iterrows():
            oid = row['oid']
            try:
                det = client.query_detections(oid, format="pandas")
                
                if not det.empty:
                    # Add spatial coordinates if available
                    det['oid'] = oid
                    if 'ra' in row and 'dec' in row:
                        det['ra'] = row['ra']
                        det['dec'] = row['dec']
                    
                    # Select columns
                    cols = ['oid', 'mjd', 'magpsf', 'fid', 'sigmapsf']
                    if 'ra' in det.columns:
                        cols.extend(['ra', 'dec'])
                    
                    clean_det = det[cols]
                    batch_detections.append(clean_det)
                    processed_oids_batch.append(oid)
                    
            except Exception as e:
                print(f"Error fetching {oid}: {e}")
                continue
        
        if batch_detections:
            result_df = pd.concat(batch_detections, ignore_index=True)
            print(f"Page {page_number}: Retrieved {len(result_df)} detections from {len(processed_oids_batch)} objects")
            return result_df, processed_oids_batch
        else:
            print(f"Page {page_number}: No detections retrieved")
            return pd.DataFrame(), []
            
    except Exception as e:
        print(f"Page {page_number}: Batch fetch failed - {e}")
        return pd.DataFrame(), []

@task(name="Save to DuckDB")
def save_batch(df, processed_oids):
    """Inserts data using INSERT OR IGNORE to handle duplicates."""
    if df.empty:
        return 0
    
    con = duckdb.connect(DB_NAME)
    
    try:
        # Insert detections - explicitly specify columns (without inserted_at)
        con.execute("""
            INSERT OR IGNORE INTO supernovae (oid, mjd, magpsf, fid, sigmapsf, ra, dec)
            SELECT oid, mjd, magpsf, fid, sigmapsf, ra, dec FROM df
        """)
        
        # Mark candidates as processed
        if processed_oids:
            oids_df = pd.DataFrame({'oid': processed_oids})
            con.execute("INSERT OR IGNORE INTO processed_candidates (oid) SELECT * FROM oids_df")
        
        # Get new total
        total = con.execute("SELECT COUNT(*) FROM supernovae").fetchone()[0]
        print(f"Saved {len(df)} detections. Total records: {total:,}")
        
    except Exception as e:
        print(f"Save failed: {e}")
        total = 0
    finally:
        con.close()
    
    return total

# == FLOW == 
# 3) Main Harvesting Loop with resume capability (in case of interruptions):
@flow(name="Supernova Ingestion Loop", log_prints=True)
def start_harvest():
    """Main loop with resume capability."""
    
    current_count, processed_count = init_db()
    processed_oids = get_processed_oids()
    
    page = 1
    empty_pages = 0
    max_empty_pages = 5  # Stop after 5 consecutive empty pages
    
    print("="*60)
    print("Starting supernova data harvest...")
    print(f"Target: {TARGET_RECORDS:,} detection records")
    print(f"Current: {current_count:,} records")
    print(f"Already processed: {processed_count:,} candidates")
    print("="*60)
    
    start_time = time.time()
    
    while current_count < TARGET_RECORDS: # Main loop
        # Fetch
        new_data, new_oids = fetch_batch(page, processed_oids)
        
        # Save:
        if not new_data.empty:
            current_count = save_batch(new_data, new_oids)
            processed_oids.update(new_oids)  # Update in-memory set
            
            progress = (current_count / TARGET_RECORDS) * 100
            elapsed = time.time() - start_time
            rate = current_count / elapsed if elapsed > 0 else 0
            
            print(f"Progress: {current_count:,}/{TARGET_RECORDS:,} ({progress:.1f}%) | Rate: {rate:.0f} records/sec")
            
            empty_pages = 0  # Reset counter
        else:
            empty_pages += 1
            print(f"Empty batch ({empty_pages}/{max_empty_pages})")
            
            if empty_pages >= max_empty_pages:
                print("Stopping: Too many consecutive empty pages")
                break
        
        # Increment and rate limit
        page += 1
        time.sleep(3.0)  # Sleep timer to handle throttling
    
    elapsed_total = time.time() - start_time
    print("="*60)
    print(f"DATA INGESTION COMPLETE!")
    print(f"Final count: {current_count:,} records")
    print(f"Total time: {elapsed_total/60:.1f} minutes")
    print("="*60)

if __name__ == "__main__":
    start_harvest()