import random
while True:
    try:
        player_input = int(input("Hlava (1) / Znak (2): "))
        coin = random.randint(1,2)

        if player_input == coin:
            print("You won!")
        else:
            print("You lost!")
    except ValueError:
        print("You must enter a number!")