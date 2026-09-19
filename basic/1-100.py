import random

number = random.randint(1,99)
while True:
    try:
        guess = int(input("Take a guess: "))    
        if guess > number:
            print("The number you're looking for is LOWER")
        elif guess < number:
            print("The number you're looking for is HIGHER")
        else:
            print("You won!")
            break
    except ValueError:
        print("Not valid")
    