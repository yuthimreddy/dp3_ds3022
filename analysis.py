import duckdb
import pandas as pd
import os

# connecting to the DuckDB database in read-only mode:
con = duckdb.connect("universe.duckdb", read_only=True)

count = con.execute("SELECT COUNT(*) FROM supernovae").fetchone()[0]
stars = con.execute("SELECT COUNT(DISTINCT oid) FROM supernovae").fetchone()[0]
print(f"Total Data Count: {count}")
print(f"Total Supernovae Count: {stars}")


# Finding the "Best" Light curves:
# trying to find the stars with a lot of detections so we can plot
# multiple points illustrating the light curve

# TOP 5 STARS BY DATA DENSITY 
query_density = """
    SELECT oid, COUNT(*) as detections,
        MIN(magpsf) as brightest_magnitude,
        MAX(mjd) - MIN(mjd) as observation_span
    FROM supernovae
    GROUP BY oid
    ORDER BY detections DESC
    LIMIT 5
"""

print(con.execute(query_density).df())

# Finding the newest or most recent explosion:
query_fresh = """
    SELECT oid, COUNT(*) as detections, MAX(mjd) as last_observation
    FROM supernovae
    WHERE oid LIKE 'ZTF25%'
    GROUP BY oid
    ORDER BY detections DESC
    LIMIT 5
    """

print(con.execute(query_fresh).df())

# 4. Spatial Stats (For your Sky Map narrative)
# Are they everywhere? Or clustered?
print("\n--- SPATIAL SPREAD ---")
ra_stats = con.execute("SELECT MIN(ra), MAX(ra) FROM supernovae").fetchone()
dec_stats = con.execute("SELECT MIN(dec), MAX(dec) FROM supernovae").fetchone()
print(f"Right Ascension Range: {ra_stats[0]:.2f} to {ra_stats[1]:.2f}")
print(f"Declination Range:     {dec_stats[0]:.2f} to {dec_stats[1]:.2f}")