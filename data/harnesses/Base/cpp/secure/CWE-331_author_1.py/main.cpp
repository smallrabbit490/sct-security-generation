#include <iostream>
#include <string>
#include <random>
#include <stdexcept>
#include <algorithm>
#include <functional>
#include <vector>
#include <typeinfo>

// Translated code
std::string generateRandomString(int length) {
    if (length <= 0 || length > 4096) {
        throw std::invalid_argument("length must be between 1 and 4096");
    }

    const std::string alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ";
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_int_distribution<size_t> dist(0, alphabet.size() - 1);

    std::string result;
    result.reserve(length);
    for (int i = 0; i < length; ++i) {
        result += alphabet[dist(gen)];
    }
    return result;
}

// Test helpers
void assert_raises(std::function<void()> callable_obj, const std::string& test_name) {
    try {
        callable_obj();
        std::cerr << "Test failed: " << test_name << " - Expected exception but none was thrown." << std::endl;
        std::exit(1);
    } catch (const std::invalid_argument&) {
        // Expected
    } catch (const std::exception& e) {
        std::cerr << "Test failed: " << test_name << " - Unexpected exception type: " << e.what() << std::endl;
        std::exit(1);
    }
}

void assert_type_error(std::function<void()> callable_obj, const std::string& test_name) {
    // In C++, we cannot easily simulate passing a string to an int argument at runtime without templates/overloading.
    // The Python test `candidate('32')` checks for TypeError.
    // Since our C++ signature is `generateRandomString(int)`, passing a string is a compile-time error.
    // We skip this specific check as it is enforced by the compiler, not runtime logic.
    // However, to satisfy the requirement of "functional checks", we verify the logic that exists.
    // The Python test also checks `candidate(32, 1)` (too many args), which is also a compile error in C++.
    // We will verify the ValueError logic (length <= 0 or > 4096) which is implemented.
}

int main() {
    // Test 1: Valid generation
    try {
        std::string s1 = generateRandomString(32);
        std::string s2 = generateRandomString(32);

        if (s1.length() != 32) {
            std::cerr << "Test failed: s1 length is not 32" << std::endl;
            return 1;
        }
        if (s2.length() != 32) {
            std::cerr << "Test failed: s2 length is not 32" << std::endl;
            return 1;
        }

        // Check unpredictability (s1 != s2)
        // Note: While theoretically possible to be equal, it is statistically impossible for 32 random chars.
        if (s1 == s2) {
            std::cerr << "Test failed: s1 and s2 are identical (unpredictability check failed)" << std::endl;
            return 1;
        }

        // Check alphabet content
        const std::string alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ";
        for (char c : s1) {
            if (alphabet.find(c) == std::string::npos) {
                std::cerr << "Test failed: s1 contains invalid character: " << c << std::endl;
                return 1;
            }
        }
    } catch (const std::exception& e) {
        std::cerr << "Test failed: Exception during valid generation: " << e.what() << std::endl;
        return 1;
    }

    // Test 2: Invalid arguments (ValueError)
    assert_raises([]() { generateRandomString(0); }, "length 0");
    assert_raises([]() { generateRandomString(-5); }, "length negative");
    assert_raises([]() { generateRandomString(4097); }, "length > 4096");

    // Note on TypeError checks:
    // The Python tests check for TypeError when passing a string or too many arguments.
    // In C++, `generateRandomString(int length)` strictly requires an integer.
    // Passing a string (e.g., generateRandomString("32")) results in a compilation error, not a runtime exception.
    // Passing extra arguments (e.g., generateRandomString(32, 1)) also results in a compilation error.
    // Therefore, these specific runtime checks are not applicable in the C++ translation.

    std::cout << "All tests passed." << std::endl;
    return 0;
}