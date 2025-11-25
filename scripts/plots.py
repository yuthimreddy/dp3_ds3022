import duckdb
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns 
import matplotlib
import os


# Connecting to Database:
con = duckdb.connect('universe.duckdb', read_only=True)
print("Connected to database...")

# -- FILTERING DATA FOR PLOTTING -- 

matplotlib.rcParams["font.family"] = 'Times New Roman'

# PLOT 1: SKYMAP GALACTIC MAP
# ==========================================
print("Generating Sky Map...")

# Figure size: (choosing mollweide projection for full-sky view)
plt.figure(figsize=(12, 7))
ax = plt.subplot(111, projection="mollweide")

# -- DATA PREPARATION --

# Fetch RA/Dec for all stars
map_query = """
    SELECT oid, AVG(ra) as ra, AVG(dec) as dec 
    FROM supernovae GROUP BY oid
"""
df_map = con.execute(map_query).df()

# shifting RA so the map centers correctly (0-360 -> -180 to 180)
# need to convert to radians for mollweide projection
ra_rad = (df_map['ra'] - 180) * np.pi / 180
dec_rad = df_map['dec'] * np.pi / 180

# PLOTTING MAP (PLOT 1): 

# Scatter Plot:
ax.scatter(ra_rad, dec_rad, s=5, alpha=0.6, color='#E74C3C', lw=0)

# FORMATTING:
plt.title(f"ZTF Survey Footprint ({len(df_map)} Objects)", fontsize=16, weight='bold')
plt.xlabel("Right Ascension (shifted)", fontsize=12, weight='bold')
plt.ylabel("Declination", fontsize=12, weight='bold')
plt.grid(True, linestyle='--', alpha=0.3)

# The telescope is in the Northern Hemisphere (California), so it can't see the South Pole!
plt.text(0, -1.2, "Cannot see Southern Hemisphere Stars \n(Earth is in the way)", 
         horizontalalignment='center', fontsize=9, style='italic', color='gray')


# saving figure as file in an output folder:
os.makedirs("outputs", exist_ok=True)
gm_plot_filename = 'outputs/galactic_map.png'
plt.savefig(gm_plot_filename, dpi=300)
print(f"Saved 'galactic_map.png' to {gm_plot_filename}")

# ==========================================
# PLOT 2: THE LIGHT CURVE
# ==========================================

print("Generating Light Curve...")

# Looking at a specifc supernova's light curve:
# from the analysis done, we know this object has the brightest magnitude
# and a good number of detections which is good for plotting
target_oid = "ZTF24aaaisai"

# Fetching light curve data for the target_oid:
query_curve = f"""
    SELECT 
        CAST(mjd AS INT) as mjd_day, 
        AVG(magpsf) * -1 as brightness, 
        fid 
    FROM supernovae 
    WHERE oid = '{target_oid}' 
    GROUP BY mjd_day, fid
    ORDER BY mjd_day
"""
# Storing the result in a dataframe:
df_curve = con.execute(query_curve).df()

# Plotting the light curve if data is available:
if not df_curve.empty:
    plt.figure(figsize=(10, 6))
    
    # Map colors: 1=Green, 2=Red (for the two different telescope filters)
    colors = {1: '#007f5f', 2: '#e63946'}
    labels = {1: 'Green Band (g)', 2: 'Red Band (r)'}
    
    # plotting green and red separately:
    for fid, group in df_curve.groupby('fid'):
        plt.plot(group['mjd_day'], group['brightness'], marker='o', linestyle='-', 
                 color=colors[fid], label=labels[fid], alpha=0.7)

    # FORMATTING: 
    # Set the title and axis labels
    plt.suptitle("Supernova Light Curve", x = 0.22, weight = 'bold', fontsize = 20)
    plt.title(f"Focusing on observation {target_oid}",x = 0.11)
    # customizing spacing between the sup.title and title - making them closer together
    plt.subplots_adjust(top = 0.90)
        
    
    # -- LABELS --
    plt.xlabel("Time (MJD Day)", fontsize=12, weight='bold')
    plt.ylabel("Brightness (Inverted Magnitude)", fontsize=12, weight='bold')
    plt.grid(axis='both', linestyle='--', color='gray', which='both', zorder=1, alpha=0.3)

    plt.legend()

    # Remove unnecessary spines (for cleaner look)
    plt.gca().spines['top'].set_visible(False)
    plt.gca().spines['right'].set_visible(False)
    plt.gca().spines['left'].set_visible(False)
        
    # saving graph:

    lc_plot_filename = "outputs/light_curve.png"
    plt.savefig(lc_plot_filename, dpi=300)
    print(f"Saved 'light_curve.png' to {lc_plot_filename}")
else:
    print(f"Error: No data found for {target_oid}")

con.close()