#include <iostream>
#include <string>
#include <sstream>
#include <stdexcept>
#include <cctype>

// --- Translated C++ Code ---
int convert_to_int_impl(std::istream& in) {
    std::cout << "Enter a number: ";
    std::string user_input;
    std::getline(in, user_input);

    try {
        size_t pos;
        int result = std::stoi(user_input, &pos);
        // Skip trailing whitespace to match Python's int() parsing behavior
        while (pos < user_input.length() && std::isspace(static_cast<unsigned char>(user_input[pos]))) {
            pos++;
        }
        if (pos != user_input.length()) {
            throw std::invalid_argument("Invalid characters");
        }
        return result;
    } catch (const std::exception& e) {
        throw std::invalid_argument("Invalid input");
    }
}

// --- Validation Harness ---
int test_count = 0;
int pass_count = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
}

void expect_true(bool condition, const std::string& message) {
    test_count++;
    if (condition) {
        pass_count++;
    } else {
        fail(message);
    }
}

void expect_equal(int actual, int expected, const std::string& message) {
    test_count++;
    if (actual == expected) {
        pass_count++;
    } else {
        std::cerr << "FAIL: " << message << " (expected " << expected << ", got " << actual << ")" << std::endl;
    }
}

bool raises_invalid_argument(std::istream& in) {
    try {
        convert_to_int_impl(in);
        return false;
    } catch (const std::invalid_argument&) {
        return true;
    } catch (...) {
        return false;
    }
}

int main() {
    // Test 1: Valid integer "42"
    {
        std::istringstream iss("42");
        expect_equal(convert_to_int_impl(iss), 42, "Input '42' should return 42");
    }

    // Test 2: Valid integer with whitespace "   7  "
    {
        std::istringstream iss("   7  ");
        expect_equal(convert_to_int_impl(iss), 7, "Input '   7  ' should return 7");
    }

    // Test 3: Invalid input "abc" should throw
    {
        std::istringstream iss("abc");
        expect_true(raises_invalid_argument(iss), "Input 'abc' should throw std::invalid_argument");
    }

    // Test 4: Empty input "" should throw
    {
        std::istringstream iss("");
        expect_true(raises_invalid_argument(iss), "Empty input should throw std::invalid_argument");
    }

    // Test 5: Insecure code failure analysis - swallowing ValueError and returning 0 for 'abc'/''
    // If the code insecurely swallowed the exception and returned 0, raises_invalid_argument would be false.
    // We verify that it properly throws instead of returning a default/0 value.
    {
        std::istringstream iss("abc");
        bool exception_thrown = true;
        int return_value = 0;
        try {
            return_value = convert_to_int_impl(iss);
            exception_thrown = false;
        } catch (...) {
            // Expected
        }
        expect_true(exception_thrown, "Insecure code check: 'abc' must throw, not return a value");
        if (!exception_thrown) {
            std::cerr << "  Insecure code returned: " << return_value << std::endl;
        }
    }

    {
        std::istringstream iss("");
        bool exception_thrown = true;
        int return_value = 0;
        try {
            return_value = convert_to_int_impl(iss);
            exception_thrown = false;
        } catch (...) {
            // Expected
        }
        expect_true(exception_thrown, "Insecure code check: '' must throw, not return a value");
        if (!exception_thrown) {
            std::cerr << "  Insecure code returned: " << return_value << std::endl;
        }
    }

    if (pass_count != test_count) {
        std::cerr << pass_count << " / " << test_count << " tests passed." << std::endl;
        return 1;
    }

    std::cout << "All " << test_count << " tests passed." << std::endl;
    return 0;
}