def add(a: float, b: float) -> float:
    """
    Add two numbers and return the result.
    """
    return a + b


def subtract(a: float, b: float) -> float:
    """
    Subtract the second number from the first and return the result.
    """
    return a - b


def multiply(a: float, b: float) -> float:
    """
    Multiply two numbers and return the product.
    """
    return a * b


def divide(a: float, b: float) -> float:
    """
    Divide the first number by the second and return the result.
    Raises a ValueError if an attempt is made to divide by zero.
    """
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b
