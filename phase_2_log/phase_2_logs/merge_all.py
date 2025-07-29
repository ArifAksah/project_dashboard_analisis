import os
import pandas as pd

# === Configuration ===
input_folder = "./"  # Change this to your actual folder
output_file = "merged.csv"

# === Merge Process ===
all_files = [f for f in os.listdir(input_folder) if f.endswith(".csv")]

df_list = []
for file in all_files:
    file_path = os.path.join(input_folder, file)
    print(f"Reading: {file_path}")
    df = pd.read_csv(file_path, low_memory=False)
    df_list.append(df)

# Concatenate all DataFrames
merged_df = pd.concat(df_list, ignore_index=True)

# Save the merged DataFrame
merged_df.to_csv(output_file, index=False)
print(f"Saved merged file to: {output_file}")
