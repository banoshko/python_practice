# Test 2: Function + Fibonacci
# Task: Function returns nth Fibonacci number. Call it with a few values, print results.
# Time limit: 10 min

fibonacci_list = [0,1]
def fibonacci(n):
    fibonacci_list = [0,1]
    for _ in range(n-1):
        calculation = fibonacci_list[0] + fibonacci_list[1]
        fibonacci_list.pop(0)
        fibonacci_list.append(calculation)
    return(fibonacci_list[1])
print(fibonacci(5))
print(fibonacci(8))
print(fibonacci(4))

#Time: +- 10:00
#Readability: 7/10
#Improvability: 8/10
