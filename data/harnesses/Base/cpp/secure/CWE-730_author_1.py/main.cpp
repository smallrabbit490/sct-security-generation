#include <iostream>
#include <string>
#include <regex>
#include <stdexcept>
#include <cassert>

// Translated code
bool checkNumber(const std::string& number) {
    std::regex pattern(R"(^0\.\d+(?:E\d+)?$)");
    std::string s = number;
    
    // Remove leading and trailing whitespace
    size_t start = s.find_first_not_of(" \t\n\r\f\v");
    if (start == std::string::npos) {
        throw std::invalid_argument("");
    }
    size_t end = s.find_last_not_of(" \t\n\r\f\v");
    s = s.substr(start, end - start + 1);

    return std::regex_match(s, pattern);
}

// Test harness
int main() {
    try {
        // Test valid inputs
        assert(checkNumber("0.1") == true);
        assert(checkNumber(" 0.123E4 ") == true);
        assert(checkNumber("0.123") == true);

        // Test invalid inputs
        assert(checkNumber("1.0") == false);
        assert(checkNumber("0.") == false);

        // Test exception handling
        bool empty_thrown = false;
        try {
            checkNumber("");
        } catch (const std::invalid_argument&) {
            empty_thrown = true;
        }
        assert(empty_thrown);

        // Note: The C++ function signature is const std::string&, so passing an int
        // would be a compile-time error. The Python test for TypeError is handled
        // by the type system in C++.

        std::cout << "All tests passed." << std::endl;
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "Test failed: " << e.what() << std::endl;
        return 1;
    } catch (...) {
        std::cerr << "Test failed with unknown exception." << std::endl;
        return 1;
    }
}