# Test 5: JSON save/load with fallback
# Task: Load dict from saves/test.json, fallback to empty if missing, add entry, save.
# Time limit: 10 min
import json
import random
saved = []

try:
    with open("tests/saves/test.json", "r") as f:
        saved = json.load(f)
except FileNotFoundError:
    print("File not found")
except json.decoder.JSONDecodeError:
    print("File empty")
    
print(saved) 
fruit = ["apple", "banana", "pear"]
saved.append(random.choice(fruit))

try:
    with open("tests/saves/test.json", "w") as f:
        json.dump(saved, f)
except FileNotFoundError:
    print("File not found")

#Time: 9:21
#Readability: 8/10
#Improvability: 8/10