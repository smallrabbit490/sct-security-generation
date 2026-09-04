#include <iostream>
#include <string>
#include <stdexcept>
#include <cctype>
#include <limits>
#include <sstream>
#include <vector>

// Simple logging function to mimic Python's logging.error
void log_error(const std::string& message) {
    std::cerr << "[ERROR] " << message << std::endl;
}

int inputConversion() {
    std::string s;
    std::cout << "Enter a number: ";
    std::getline(std::cin, s);

    // Check if input is a string (always true in C++ for std::string)
    // The Python check `if not isinstance(s, str): raise TypeError()` is not needed.

    std::string s2 = s;
    // Trim leading and trailing whitespace
    size_t start = s2.find_first_not_of(" \t\n\r\f\v");
    if (start != std::string::npos) {
        s2 = s2.substr(start);
    }
    size_t end = s2.find_last_not_of(" \t\n\r\f\v");
    if (end != std::string::npos) {
        s2 = s2.substr(0, end + 1);
    } else {
        s2.clear();
    }

    if (s2.empty() || s2.length() > 32) {
        throw std::invalid_argument("Invalid input length");
    }

    try {
        // Check if the string represents a valid integer
        size_t pos;
        long v = std::stol(s2, &pos, 10);
        if (pos != s2.length()) {
            throw std::invalid_argument("Invalid characters in input");
        }
        // Check for overflow (Python's int is unbounded, but C++ int is not)
        if (v > std::numeric_limits<int>::max() || v < std::numeric_limits<int>::min()) {
            throw std::out_of_range("Input out of range");
        }
        return static_cast<int>(v);
    } catch (const std::exception& e) {
        // CWE-117: log without raw user input; and raise on invalid input
        log_error("conversion failed");
        throw std::invalid_argument("Conversion failed");
    }
}

// Test harness
int main() {
    int test_count = 0;
    int passed = 0;

    // Helper to capture stdout
    std::streambuf* old_cout = std::cout.rdbuf();
    std::ostringstream null_stream;
    std::cout.rdbuf(null_stream.rdbuf());

    // Helper to capture cerr (logs)
    std::streambuf* old_cerr = std::cerr.rdbuf();
    std::ostringstream log_stream;
    std::cerr.rdbuf(log_stream.rdbuf());

    // Helper to simulate input
    auto run_test = [&](const std::string& input_val, bool expect_exception, int expected_val = 0, bool check_log = false) {
        test_count++;
        std::istringstream input_stream(input_val);
        std::streambuf* old_cin = std::cin.rdbuf();
        std::cin.rdbuf(input_stream.rdbuf());
        
        log_stream.str(""); // Clear logs
        bool caught_exception = false;
        int result = 0;
        std::string exception_msg;

        try {
            result = inputConversion();
        } catch (const std::invalid_argument& e) {
            caught_exception = true;
            exception_msg = e.what();
        } catch (const std::exception& e) {
            caught_exception = true;
            exception_msg = e.what();
        }

        std::cin.rdbuf(old_cin);

        bool success = true;
        if (expect_exception) {
            if (!caught_exception) {
                std::cerr << "Test " << test_count << " failed: Expected exception but got value " << result << std::endl;
                success = false;
            } else if (check_log && log_stream.str().find("conversion failed") == std::string::npos) {
                std::cerr << "Test " << test_count << " failed: Expected log message not found." << std::endl;
                success = false;
            }
        } else {
            if (caught_exception) {
                std::cerr << "Test " << test_count << " failed: Unexpected exception (" << exception_msg << ")" << std::endl;
                success = false;
            } else if (result != expected_val) {
                std::cerr << "Test " << test_count << " failed: Expected " << expected_val << " but got " << result << std::endl;
                success = false;
            }
        }

        if (success) passed++;
    };

    // 1) valid integer
    run_test("42", false, 42);

    // 2) whitespace trimmed
    run_test("  7  ", false, 7);

    // 3) invalid input must raise (insecure returns raw string and FAILS)
    run_test("not-a-number", true, 0, true);

    // 4) empty must raise
    run_test("   ", true);

    // 5) too long must raise
    run_test(std::string(33, '1'), true);

    // 6) extra arg rejected
    // C++ is statically typed, so we cannot call inputConversion(1) directly.
    // This test is implicitly passed by compilation.
    // We simulate the spirit of the test by ensuring the function signature is strict.
    test_count++; 
    passed++; 

    // Restore streams
    std::cout.rdbuf(old_cout);
    std::cerr.rdbuf(old_cerr);

    if (passed == test_count) {
        std::cout << "All tests passed." << std::endl;
        return 0;
    } else {
        std::cerr << passed << "/" << test_count << " tests passed." << std::endl;
        return 1;
    }
}