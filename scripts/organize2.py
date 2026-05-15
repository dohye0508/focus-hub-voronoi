import os
import shutil
import glob

# Ensure these are not files
for name in ['scripts', 'results', 'data']:
    if os.path.isfile(name):
        os.remove(name)

dirs = ['data/raw', 'data/processed', 'data/spatial', 'scripts', 'results']
for d in dirs:
    os.makedirs(d, exist_ok=True)

# Move raw data
for f in glob.glob("*.xlsx"):
    shutil.move(f, f"data/raw/{f}")
for f in glob.glob("*.zip"):
    shutil.move(f, f"data/raw/{f}")

# Move processed data
for f in glob.glob("*.csv"):
    shutil.move(f, f"data/processed/{f}")

# Move spatial
if os.path.exists("전국+청소년쉼터+현황"):
    shutil.move("전국+청소년쉼터+현황", "data/spatial/")

# Move scripts
for f in glob.glob("*.py"):
    if f != "organize.py":
        shutil.move(f, f"scripts/{f}")

# Move results
for f in glob.glob("*.html"):
    shutil.move(f, f"results/{f}")
for f in glob.glob("*.txt"):
    if f != "설명.txt": # Keep the user's description
        shutil.move(f, f"results/{f}")

# Clean scratch
if os.path.exists("scratch"):
    shutil.rmtree("scratch")

print("Files organized successfully.")
