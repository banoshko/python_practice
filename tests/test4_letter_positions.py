# Test 4: Letter position finder
# Task: Function takes word+letter, prints every index where the letter appears.
# Time limit: 10 min

def find_positions(word, letter):
    position = 0
    for i in word:
        if i == letter:
            print(f"The index of the letter youre looking for is {position}")
        position += 1

find_positions("apple", "p")

#Time: 6:47
#Readability: 8/10
#Improvability: 8/10