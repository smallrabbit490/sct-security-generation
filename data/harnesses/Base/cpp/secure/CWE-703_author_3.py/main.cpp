#include <iostream>
#include <string>
#include <stdexcept>
#include <limits>
#include <sstream>
#include <vector>

// Translated function
int inputInt() {
    std::cout << "Enter a number: ";
    std::string s;
    if (!(std::cin >> s)) {
        throw std::runtime_error("Input failed");
    }

    try {
        size_t pos;
        long v = std::stol(s, &pos);
        if (pos != s.length()) {
            throw std::invalid_argument("Invalid characters");
        }

        if (v < 0 || v > std::numeric_limits<int>::max()) {
            throw std::out_of_range("Value out of range");
        }

        return static_cast<int>(v);
    } catch (const std::exception& e) {
        throw std::invalid_argument("Invalid input");
    }
}

// Test harness
int main() {
    struct Test {
        std::string input;
        bool should_pass;
        int expected_value;
    };

    std::vector<Test> tests = {
        {"10", true, 10},
        {"0", true, 0},
        {"abc", false, 0},
        {"-1", false, 0},
        {std::to_string(static_cast<long long>(std::numeric_limits<int>::max()) + 1), false, 0}
    };

    bool all_passed = true;

    for (const auto& test : tests) {
        std::istringstream iss(test.input);
        std::streambuf* old_cin = std::cin.rdbuf(iss.rdbuf());
        
        bool passed = false;
        try {
            int result = inputInt();
            if (test.should_pass && result == test.expected_value) {
                passed = true;
            }
        } catch (const std::invalid_argument&) {
            if (!test.should_pass) {
                passed = true;
            }
        } catch (...) {
            // Other exceptions count as failure
        }

        std::cin.rdbuf(old_cin);

        if (!passed) {
            std::cerr << "Test failed for input: " << test.input << std::endl;
            all_passed = false;
        }
    }

    // Test for TypeError equivalent (function takes no arguments)
    // In C++, calling a no-argument function with arguments is a compile-time error.
    // We simulate the logic check by ensuring the function signature is strictly int().
    // Since this is a static property, we just acknowledge it here.
    
    if (all_passed) {
        return 0;
    } else {
        return 1;
    }
}