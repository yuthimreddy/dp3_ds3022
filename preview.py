import duckdb
import pandas as pd

# Connect to your database
con = duckdb.connect("universe.duckdb", read_only=True)

# Show current counts
print("\n" + "="*60)
print("DATABASE SUMMARY")
print("="*60)

total_records = con.execute("SELECT COUNT(*) FROM supernovae").fetchone()[0]
total_candidates = con.execute("SELECT COUNT(*) FROM processed_candidates").fetchone()[0]

print(f"Total detection records: {total_records:,}")
print(f"Processed supernovae: {total_candidates:,}")
print()

# Preview first 10 records
print("SAMPLE DATA (First 10 detections):")
print("="*60)
sample = con.execute("""
    SELECT oid, mjd, magpsf, fid, ra, dec 
    FROM supernovae 
    LIMIT 10
""").df()
print(sample)
print()

# Show unique supernovae
print("UNIQUE SUPERNOVAE (First 5):")
print("="*60)
unique = con.execute("""
    SELECT oid, COUNT(*) as detections, MIN(mjd) as first_seen, MAX(mjd) as last_seen
    FROM supernovae 
    GROUP BY oid 
    LIMIT 5
""").df()
print(unique)

con.close()