# Test 3: Dictionary from input
# Task: Loop 5 times, ask name+number, add to dict, then print all with a for loop.
# Time limit: 10 min

dict = {}
for _ in range(5):
    name = input("Name: ")
    number = input("Number: ")
    dict[name] = number

for name in dict:
    print(name, ":", dict[name])

#Time: +- 10:00
#Readability: 8/10
#Improvability: 8/10