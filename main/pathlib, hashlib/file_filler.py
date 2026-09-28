from pathlib import Path
import random
folder = Path("files")
chars = [
"a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m", "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", ".", "_"
]
random_string = ""
for file in folder.iterdir():
    if file.is_file():
        for _ in range(random.randint(5,50)):
            random_choice = random.choice(chars)
            random_string = random_string + random_choice
            with open(file, "a") as f:
                file.write_text(random_string)
        print(f"File {file} filled!")
