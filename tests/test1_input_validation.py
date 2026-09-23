# Test 1: Loop + input validation
# Task: Ask for a whole number 1-10, keep asking until valid, no crash on bad input.
# Time limit: 8 min
while True:
    try:
        user = int(input("Input a number 1-10: "))
        if user > 10:
            print("Maybe try lower... ")
        elif user < 1:
            print("That's kinda low")
        else:
            print("Congratulations, you're not braindead!")
            break
    except ValueError:
        print("You must enter a number! ")

#Time: 3:10
#Readability: 7/10
#Improvability: 9/10