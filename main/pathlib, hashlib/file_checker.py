from pathlib import Path
folder = Path("files")

for file in folder.iterdir():
    if file.is_file():
        size = file.stat()

    print(f"The size of {file} is {size.st_size}")