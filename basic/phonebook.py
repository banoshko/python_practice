import json
contacts = {}

try:
    with open("saves/phonebook_memory.json", "r") as f:
        contacts = json.load(f)
except FileNotFoundError:
    contacts = {}

allowed_number_chars = "0123456789+ "

def is_valid_number(number):
    for char in number:
        if char not in allowed_number_chars:
            return False
    return True
def save():
    try:
        with open("saves/phonebook_memory.json", "w") as f:
            json.dump(contacts, f)
    except FileNotFoundError:
        print("File not found.")

while True:
    try:
        user = int(input("--------------------\n1. Add Contact\n2. View Contacts\n3. Delete Contact\n4. Exit\n--------------------\nProvide your choice: "))
        if user == 1:
            name = input("--------------------\nEnter name: ")
            name = name.strip().capitalize()
            number = input("Enter number: ").strip()
            if number == "":
                print("--------------------\nYou didn't provide a number!")
            elif name == "":
                print("--------------------\nYou didn't provide a name!")
            elif not is_valid_number(number):
                print("--------------------\nYou used invalid characters!")
            else:
                try:
                    print("--------------------")
                    contacts[name] = number
                    save()
                    print(f"{name} has been added to your contacts!")
                except Exception:
                    print("--------------------\nInvalid input.")

        elif user == 2:
            if contacts == {}:
                print("--------------------\nNo contacts yet!")
            else:
                    
                position = 1

                try:
                    print("--------------------\nYour contacts:")
                    for name in sorted(contacts, key=str.lower):
                        print(f"{position}. {name} : {contacts[name]}")
                        position += 1
                except:
                    print("Invalid input.")

        elif user ==3:
            name = input("--------------------\nWhat contact would you like to delete? ")
            name = name.strip().capitalize()
            if name not in contacts:
                print("--------------------\nWe don't have him around here")
            else:
                try:
                    contacts.pop(name)
                    print(f"{name} has been removed from your contacts!")
                    save()
                except Exception:
                    print("--------------------\nSomething went wrong")

        elif user == 4:
            print("--------------------\nBye bye\n--------------------")
            break

        else:
            print("--------------------\nInvalid input.")
    except ValueError:
        print("--------------------\nInvalid input.")