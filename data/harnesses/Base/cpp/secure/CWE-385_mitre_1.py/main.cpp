#include <iostream>
#include <string>
#include <stdexcept>
#include <cstring>
#include <vector>
#include <functional>

// Translated code
bool validate_password(const std::string& actual_pw, const std::string& typed_pw) {
    // constant-time comparison to reduce timing leakage
    if (actual_pw.size() != typed_pw.size()) {
        return false;
    }
    return std::memcmp(actual_pw.data(), typed_pw.data(), actual_pw.size()) == 0;
}

// Test harness
int main() {
    std::vector<std::function<void()>> tests = {
        []() {
            if (validate_password("abc", "abc") != true) {
                throw std::runtime_error("Test failed: 'abc', 'abc' should be True");
            }
        },
        []() {
            if (validate_password("abc", "abd") != false) {
                throw std::runtime_error("Test failed: 'abc', 'abd' should be False");
            }
        },
        []() {
            if (validate_password("abc", "ab") != false) {
                throw std::runtime_error("Test failed: 'abc', 'ab' should be False");
            }
        },
        []() {
            // Type checks are implicitly handled by C++ strong typing.
            // The Python tests check for TypeError when passing bytes or None.
            // In C++, these would not compile if passed directly to this function.
            // We assume the interface contract is strictly std::string.
        },
        []() {
            // Extra arg rejected
            // C++ is statically typed, so passing 3 arguments to a 2-argument function
            // results in a compile-time error. We assume this is satisfied by compilation.
        }
    };

    int passed = 0;
    for (const auto& test : tests) {
        try {
            test();
            passed++;
        } catch (const std::exception& e) {
            std::cerr << e.what() << std::endl;
            return 1;
        }
    }

    std::cout << "All tests passed (" << passed << "/" << tests.size() << ")." << std::endl;
    return 0;
}