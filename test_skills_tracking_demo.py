

def complex_function(x, y, z):
    if x > 0:
        if y > 0:
            if z > 0:
                result = x + y + z
                if result > 10:
                    if x < 100:
                        return result * 2
                    else:
                        return result
                else:
                    return result
            else:
                return 0
        else:
            return 0
    else:
        return 0


def missing_annotations(a, b, c):
    temp = a + b
    result = temp * c
    return result


import os
import sys
from pathlib import Path


def unused_variables():
    unused_var = "this is never used"
    another_unused = 42
    return "hello"


def function_one():
    data = [1, 2, 3, 4, 5]
    result = 0
    for item in data:
        result += item
    return result


def function_two():
    data = [1, 2, 3, 4, 5]
    result = 0
    for item in data:
        result += item
    return result
