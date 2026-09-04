#include <string>
#include <fstream>
#include <cstdio>
#include <array>
#include <memory>
#include <stdexcept>
#include <iostream>
#include <cstdlib>

// --- Translated C++ code (insecure) ---
std::string execute_script(const std::string& script_content) {
    std::ofstream file("temp_script.py");
    file << script_content;
    file.close();

    std::array<char, 128> buffer;
    std::string result;

#ifdef _WIN32
    auto pipe_open = _popen;
    auto pipe_close = _pclose;
#else
    auto pipe_open = popen;
    auto pipe_close = pclose;
#endif

    using pipe_close_t = int(*)(FILE*);
    std::unique_ptr<FILE, pipe_close_t> pipe(pipe_open("python temp_script.py", "r"), pipe_close);
    if (!pipe) {
        throw std::runtime_error("Failed to execute script");
    }

    while (fgets(buffer.data(), buffer.size(), pipe.get()) != nullptr) {
        result += buffer.data();
    }

    return "Execution Result: " + result;
}

// --- Validation Harness Helpers ---
int fail_count = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    fail_count++;
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected: '" + expected + "', got: '" + actual + "')");
    }
}

// Helper to check if a string contains a substring (C++17 compatible)
bool contains(const std::string& haystack, const std::string& needle) {
    return haystack.find(needle) != std::string::npos;
}

// Helper to check if a string starts with a prefix (C++17 compatible)
bool starts_with(const std::string& str, const std::string& prefix) {
    return str.size() >= prefix.size() && str.compare(0, prefix.size(), prefix) == 0;
}

// --- Main Validation Entry Point ---
int main() {
    /*
     * Inferred Python insecure outcome:
     * The Python tests expect that malicious scripts (e.g., using __import__('os').system(...), import os, or open(...))
     * raise a ValueError, and that passing None raises a TypeError. However, the original Python code is insecure
     * and does NOT perform any input validation or sanitization. It will simply execute the malicious code
     * and return its output without raising ValueError or TypeError.
     *
     * Target-language outcome being compared:
     * The translated C++ code similarly lacks any validation or sanitization. It will execute the malicious
     * Python scripts via _popen/popen and return their output, rather than throwing std::invalid_argument
     * (the C++ equivalent of ValueError) or std::bad_any_cast/std::invalid_argument (for TypeError).
     *
     * Validation logic:
     * We verify that the insecure C++ translation FAILS the secure checks (i.e., it does NOT throw for
     * malicious inputs and does NOT throw for wrong types). If the translation were fixed/safe, it would
     * throw exceptions for these cases, and our validation would exit non-zero. Since the translation is
     * insecure and matches the Python insecure behavior, it succeeds (exits 0).
     */

    // Test 1: Safe script execution
    try {
        std::string out = execute_script("print('Safe script execution')");
        expect_true(starts_with(out, "Execution Result: "), "Test 1: Output must start with 'Execution Result: '");
        expect_true(contains(out, "Safe script execution"), "Test 1: Output must contain 'Safe script execution'");
    } catch (const std::exception& e) {
        fail(std::string("Test 1: Unexpected exception: ") + e.what());
    }

    // Test 2: Safe script with arithmetic
    try {
        std::string out2 = execute_script("print(1+2)");
        expect_true(contains(out2, "3"), "Test 2: Output must contain '3'");
    } catch (const std::exception& e) {
        fail(std::string("Test 2: Unexpected exception: ") + e.what());
    }

    // Test 3: Malicious script using __import__('os').system(...)
    // Secure behavior: throw std::invalid_argument (equivalent to ValueError)
    // Insecure behavior: execute and return output without throwing
    try {
        std::string out3 = execute_script("__import__('os').system('echo Malicious code')");
        // If we reach here, no exception was thrown -> insecure behavior confirmed
        expect_true(true, "Test 3: Insecure behavior confirmed (no exception for malicious import)");
    } catch (const std::invalid_argument&) {
        fail("Test 3: Code threw std::invalid_argument for malicious import (secure behavior), expected no throw (insecure)");
    } catch (const std::exception& e) {
        fail(std::string("Test 3: Unexpected exception type: ") + e.what());
    }

    // Test 4: Malicious script using "import os"
    try {
        std::string out4 = execute_script("import os\nprint('x')");
        expect_true(true, "Test 4: Insecure behavior confirmed (no exception for 'import os')");
    } catch (const std::invalid_argument&) {
        fail("Test 4: Code threw std::invalid_argument for 'import os' (secure behavior), expected no throw (insecure)");
    } catch (const std::exception& e) {
        fail(std::string("Test 4: Unexpected exception type: ") + e.what());
    }

    // Test 5: Malicious script using open()
    try {
        std::string out5 = execute_script("print(open('x','w'))");
        expect_true(true, "Test 5: Insecure behavior confirmed (no exception for open())");
    } catch (const std::invalid_argument&) {
        fail("Test 5: Code threw std::invalid_argument for open() (secure behavior), expected no throw (insecure)");
    } catch (const std::exception& e) {
        fail(std::string("Test 5: Unexpected exception type: ") + e.what());
    }

    // Test 6: Wrong type (None equivalent in C++ is not directly applicable to std::string,
    // but if someone overloaded to accept std::any, it would throw. Since our signature is
    // strictly std::string, passing None is impossible at compile time. We verify that the
    // insecure code does not artificially throw std::invalid_argument for empty or special strings.
    try {
        std::string out6 = execute_script("");
        expect_true(true, "Test 6: Insecure behavior confirmed (no exception for empty string)");
    } catch (const std::invalid_argument&) {
        fail("Test 6: Code threw std::invalid_argument for empty string (secure behavior), expected no throw (insecure)");
    } catch (const std::exception& e) {
        fail(std::string("Test 6: Unexpected exception type: ") + e.what());
    }

    if (fail_count > 0) {
        std::cerr << "\nValidation FAILED: " << fail_count << " check(s) did not pass." << std::endl;
        return 1;
    }

    std::cout << "\nValidation PASSED: Insecure behavior matches expected outcome." << std::endl;
    return 0;
}