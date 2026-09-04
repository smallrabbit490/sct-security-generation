#include <iostream>
#include <stdexcept>
#include <string>
#include <cassert>

long long getFibonacci(int n) {
    if (n <= 0) {
        throw std::invalid_argument("n must be a positive integer");
    }
    if (n <= 2) {
        return 1;
    }

    long long a = 1;
    long long b = 1;
    int i = 2;
    while (i < n) {
        long long temp = a + b;
        a = b;
        b = temp;
        ++i;
    }
    return b;
}

// Overload to handle string input for type checking simulation
long long getFibonacci(std::string n) {
    throw std::invalid_argument("Invalid type");
}

int main() {
    try {
        // Test valid inputs
        assert(getFibonacci(1) == 1);
        assert(getFibonacci(2) == 1);
        assert(getFibonacci(5) == 5);
        assert(getFibonacci(10) == 55);

        // Test invalid inputs (ValueError equivalent)
        bool caught = false;
        try {
            getFibonacci(0);
        } catch (const std::invalid_argument&) {
            caught = true;
        }
        assert(caught);

        caught = false;
        try {
            getFibonacci(-1);
        } catch (const std::invalid_argument&) {
            caught = true;
        }
        assert(caught);

        // Test invalid inputs (TypeError equivalent)
        caught = false;
        try {
            getFibonacci(std::string("3"));
        } catch (const std::invalid_argument&) {
            caught = true;
        }
        assert(caught);

        std::cout << "All tests passed." << std::endl;
        return 0;
    } catch (...) {
        std::cerr << "Tests failed." << std::endl;
        return 1;
    }
}