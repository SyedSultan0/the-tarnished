from pathlib import Path

data_path = Path("data")

for folder in data_path.iterdir():
    if folder.is_dir():
        images = list(folder.glob("*"))
        print(f"{folder.name}: {len(images)} images")