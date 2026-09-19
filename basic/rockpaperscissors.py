import random
import json

try:
    with open("saves/rockpaperscissors_memory.json", "r") as f:
        score = json.load(f)
except FileNotFoundError:
    score: int = 0

def get_result(player, bot):
    global score
    player = player.lower()
    if player in shortcuts:
        player = shortcuts[player]
    if player == bot:
        q = "Tie."
    elif player == "rock" and bot == "paper" or player == "paper" and bot == "scissors" or player == "scissors" and bot == "rock":
        if score == 0:
            pass
        else:
            score -=1
        q = "You have lost."
    elif player == "paper" and bot == "rock" or player == "scissors" and bot == "paper" or player == "rock" and bot == "scissors":
        score += 1 
        q = "You have won."
    with open("saves/rockpaperscissors_memory.json", "w") as f:
        json.dump(score, f)
    try:
        return q
    except Exception:
        print("Something went wrong")
shortcuts = {
    "1": "rock", "2": "paper", "3": "scissors"
}
print("You can always quick by pressing 'Q'")
while True:
    bot_input = random.choice(["rock", "paper", "scissors"])
    player_input = input("Choose between ROCK (1), PAPER (2) and SCISSORS (3): ")
    if player_input.lower() == "q":
        print(f"Final score: {score}")
        break
    else:
        result = (get_result(player_input, bot_input))


        if result == None:
            print("Something went wrong.")
        else:
            print(f"{result} Your score is: {score}")