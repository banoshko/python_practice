import json
contacts = {}

try:
    with open("saves/phonebook_memory.json", "r") as f:
        contacts = json.load(f)
except FileNotFoundError:
    contacts = {}

while True:
    try:
        user = int(input("--------------------\n1. Add Contact\n2. Search Contacts\n3. Delete Contact\n4. Exit\n--------------------\nProvide your choice: "))
        if user == 1:
            try:
                name = input("--------------------\nEnter name: ")
                number = (input("Enter number: "))
                print("--------------------")
                contacts[name] = number
                with open("saves/phonebook_memory.json", "w") as f:
                    json.dump(contacts, f)
                print(f"{name} has been added to your contacts!")
            except Exception:
                print("--------------------\nInvalid input.")
        elif user == 2:
            try:
                print(f"--------------------\nYour contacts are:\n{contacts}")
            except:
                print("--------------------\nInvalid input.")
        elif user ==3:
            try:
                name = input("--------------------\nWhat contact would you like to delete? ")
                contacts.pop(name)
                print(f"{name} has been removed from your contacts!")
                with open("saves/phonebook_memory.json", "w") as f:
                    json.dump(contacts, f)
            except Exception:
                print("--------------------\nInvalid input.")
        elif user == 4:
            print("--------------------\nBye bye\n--------------------")
            break
        else:
            print("--------------------\nInvalid input.")
    except ValueError:
        print("--------------------\nInvalid input.")