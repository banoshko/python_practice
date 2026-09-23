import random
import json

words = ["apple", "hotel"]

word = random.choice(words)
tries = 20
wrong_guesses = 0
wrong_letters = []
guess = ()
hidden = (int(len(word)) * [" - "])
display = (int(len(word)) * [" - "])
print("".join(display))

stats = {"stats_wins" : 0, "stats_fails" : 0}
try:
    with open("saves/hangman_memory.json", "r") as f:
        stats = json.load(f)
except FileNotFoundError:
    print("File not found.")

def save():
    try:
        with open("saves/hangman_memory.json", "w") as f:
            json.dump(stats, f)
    except FileNotFoundError:
        print("File not found.")

while wrong_guesses != tries and ("".join(hidden)) != word:
    guess = input("Take a guess: ").strip().capitalize()

    if int(len(guess)) > 1:
        print("You can only guess by the letter!")
    elif guess in wrong_letters:
        print("You already guessed that letter!")
    elif guess not in word:
        wrong_guesses +=1
        print(f"Guessed wrong! Guesses remaining: {tries-wrong_guesses}")
        wrong_letters.append(guess)
    elif guess == (""):
        pass
    elif guess in hidden:
        print("You already guessed that letter!")
    else:
        print("Guessed right!")
        for i in range(len(word)):
            if word[i] == guess:
                display[i] = (f" {guess} ")
                hidden[i] = (guess)
    print("".join(display))
 
if ("".join(hidden)) == word:   
    print(f"You won! The word was: {word}")
    stats['stats_wins'] += 1
    print(f"You won {stats['stats_wins']} time(s) and failed {stats['stats_fails']} time(s)")
    save()
else:   
    print(f"You lost! The word was: {word}")
    stats['stats_fails'] += 1
    print(f"You won {stats['stats_wins']} time(s) and failed {stats['stats_fails']} time(s)")
    save()