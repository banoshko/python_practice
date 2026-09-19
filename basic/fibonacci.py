while True:
    try:
        number = int(input("Provide a number for fibonaccisation: "))
        if number < 0:
            print("We're working with positive numbers here")
        else:
            start = [0,1]

            for _ in range(number):
                steps = start[0] + start[1]
                start.append(steps)
                start.pop(0)

            print(start[0])
    except ValueError:
        print("Not a valid number.")
