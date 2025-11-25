import duckdb
import pandas as pd
import numpy as np
from datetime import datetime
import os

# connecting to the DuckDB database in read-only mode:
con = duckdb.connect("universe.duckdb", read_only=True)

# --- DATASET OVERVIEW ---
count = con.execute("SELECT COUNT(*) FROM supernovae").fetchone()[0]
stars = con.execute("SELECT COUNT(DISTINCT oid) FROM supernovae").fetchone()[0]
avg_detections = count / stars

print(f"Total Data Count: {count}") # this is the number of total detections pulled
print(f"Total Supernovae Count: {stars}") # number of UNIQUE supernovae, so out of the
print(f"Average Detections per Supernova: {avg_detections:.2f}")

# Overall Time Range:
time_range = con.execute("""
    SELECT
        MIN(mjd) as first_observation,
        MAX(mjd) as last_observation,
        MAX(mjd) - MIN(mjd) as total_span
    FROM supernovae
""").fetchone()

print(f"Observation Time Range: {time_range[2]:.0f} days")
print(f"First Observation (MJD):   {time_range[0]:.2f}")
print(f"Latest Observation (MJD):  {time_range[1]:.2f}")

# ---- ANALYSIS QUERIES ----

# --- Looking at SAMPLING DENSITY ---

# Calculating the IQR of detection counts per object:
density_stats = con.execute("""
    WITH detection_counts AS (
        SELECT oid, COUNT(*) as detections
        FROM supernovae
        GROUP BY oid
    )
    SELECT
        MIN(detections) as min_det,
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY detections) as q1,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY detections) as median,
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY detections) as q3,
        MAX(detections) as max_det,
        AVG(detections) as mean, 
        COUNT(CASE WHEN detections >= 50 THEN 1 END) as high_density_count,
        COUNT(*) as total_objects
    FROM detection_counts
""").fetchone()

# Observations with over 50 detections are considered 'high density', meaning they are suitable
# for detailed light curve analysis and graphing.
print(f"\n Detections per Supernova:")
print(f"Minimum:    {density_stats[0]}")
print(f"Q1:         {density_stats[1]:.0f}")
print(f"Median:     {density_stats[2]:.0f}")
print(f"Mean:       {density_stats[5]:.0f}")
print(f"Q3:         {density_stats[3]:.0f}")
print(f"Maximum:    {density_stats[4]}")

well_sampled_pct = (density_stats[6] / density_stats[7]) * 100
print(f"\n   Well-Sampled Objects (≥50 detections): {density_stats[6]:,} ({well_sampled_pct:.1f}%)")

# ---- BRIGHTNESS ANALYSIS ----

# Finding the "Best" Light curves:

brightness_stats = con.execute("""
    WITH peak_mags AS (
        SELECT oid, MIN(magpsf) as peak_magnitude
        FROM supernovae
        GROUP BY oid
        HAVING peak_magnitude IS NOT NULL
    )
    SELECT
        MIN(peak_magnitude) as brightest,
        MAX(peak_magnitude) as faintest,
        AVG(peak_magnitude) as avg_peak_magnitude,
        COUNT(CASE WHEN peak_magnitude BETWEEN 19 AND 20 THEN 1 END) as in_peak_range,
        COUNT(*) as total_objects
    FROM peak_mags
""").fetchone()

# Brightness scale is inverted, meaning that a lower magnitude value indicates a brighter object.
print(f"\n Peak Magnitude Stats:")
print(f"Brightest Peak Magnitude: {brightness_stats[0]:.2f}")
print(f"Faintest Peak Magnitude:  {brightness_stats[1]:.2f}")
print(f"Average Peak Magnitude:   {brightness_stats[2]:.2f}")

peak_range_pct = (brightness_stats[3] / brightness_stats[4]) * 100
print(f"\n   Objects with Peak Magnitude between 19 and 20: {brightness_stats[3]:,} ({peak_range_pct:.1f}%)")


# TOP 5 STARS BY DATA DENSITY: objects with the most observations 
query_density = con.execute("""
    SELECT oid, COUNT(*) as detections,
        MIN(magpsf) as brightest_magnitude,
        MAX(mjd) - MIN(mjd) as observation_span
    FROM supernovae
    GROUP BY oid
    ORDER BY detections DESC
    LIMIT 5
""").df()

print("\n--- TOP 5 DENSEST OBSERVATIONS ---")
print(query_density)

# TOP 5 NEWEST EXPLOSIONS:
# --- Most recently observed objects

recent_discoveries = con.execute("""
    SELECT 
        oid,
        COUNT(*) as detections,
        MIN(magpsf) as peak_mag,
        MAX(mjd) as last_observation
    FROM supernovae
    WHERE oid LIKE 'ZTF25%'
    GROUP BY oid
    ORDER BY detections DESC
    LIMIT 5
""").df()

print(f"\n   Top 5 Well-Observed 2025 Discoveries:\n")
print(f"   {'OID':<15} {'Detections':<12} {'Peak Mag':<11} {'Latest MJD'}")
print(f"   {'-'*15} {'-'*12} {'-'*11} {'-'*11}")
for _, row in recent_discoveries.iterrows():
    print(f"   {row['oid']:<15} {row['detections']:<12} {row['peak_mag']:<11.2f} {row['last_observation']:.2f}")


# Spatial ANALYSIS (right ascension, declination):
#   - useful for making sky maps and understanding the coverage of the telescope survey
#   - are the observations clustered in certain areas of the sky or evenly distributed?
print("\n--- SPATIAL SPREAD ---")

# Right Ascension (RA - east/west) and Declination (north/south) ranges:
ra_stats = con.execute("SELECT MIN(ra), MAX(ra) FROM supernovae").fetchone()
dec_stats = con.execute("SELECT MIN(dec), MAX(dec) FROM supernovae").fetchone()
print(f"Right Ascension Range: {ra_stats[0]:.2f} to {ra_stats[1]:.2f}")
print(f"Declination Range:     {dec_stats[0]:.2f} to {dec_stats[1]:.2f}")


con.close()