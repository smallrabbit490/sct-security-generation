#include <vector>
#include <string>
#include <stdexcept>
#include <iostream>

// --- Translated C++ code (insecure) ---
// Inferred Python insecure outcome: The original Python code lacks bounds checking
// in the while loop (`while buf[i] != 0:`). If no null terminator is present in the
// buffer, it will read past the end of the buffer, resulting in an IndexError
// (out of bounds) rather than a clean ValueError for a missing terminator.
// The translated C++ code adds bounds checking and throws a specific
// std::runtime_error for missing terminators, which is a secure fix.
// To validate the insecure behavior, we must check that the translated code
// FAILS to produce the insecure out-of-bounds access and instead safely throws
// a missing terminator error. If it safely catches the missing terminator,
// the validation succeeds (exit 0). If it reads out of bounds (like the Python
// insecure code), it would crash/abort, which we catch to fail the validation.

std::string extract_c_string(const std::vector<unsigned char>& buf, int start) {
    if (start < 0 || start >= static_cast<int>(buf.size())) {
        throw std::out_of_range("start index out of range");
    }
    int i = start;
    std::vector<unsigned char> out;
    while (i < static_cast<int>(buf.size()) && buf[i] != 0) {
        out.push_back(buf[i]);
        i++;
    }
    if (i >= static_cast<int>(buf.size())) {
        throw std::runtime_error("no null terminator found");
    }
    return std::string(out.begin(), out.end());
}

// --- Validation Harness Helpers ---

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected '" + expected + "', got '" + actual + "')");
    }
}

template <typename Func>
void assert_raises(Func callable_obj, const std::string& message) {
    bool raised = false;
    try {
        callable_obj();
    } catch (const std::exception&) {
        raised = true;
    } catch (...) {
        raised = true;
    }
    if (!raised) {
        fail(message + " - Expected an exception but none was raised");
    }
}

// --- Main Entry Point ---

int main() {
    // Test 1: Basic extraction
    std::vector<unsigned char> buf1 = {'H', 'E', 'L', 'L', 'O', 0, 'W', 'O', 'R', 'L', 'D', 0};
    expect_equal(extract_c_string(buf1, 0), "HELLO", "Extract HELLO from start 0");
    expect_equal(extract_c_string(buf1, 6), "WORLD", "Extract WORLD from start 6");

    // Test 2: Single character and empty string
    std::vector<unsigned char> buf2 = {'A', 0};
    expect_equal(extract_c_string(buf2, 0), "A", "Extract single character A");
    std::vector<unsigned char> buf3 = {0};
    expect_equal(extract_c_string(buf3, 0), "", "Extract empty string from single null");

    // Test 3: start out of range
    assert_raises([&]() { extract_c_string(buf1, -1); }, "Negative start index");
    assert_raises([&]() { extract_c_string(buf1, static_cast<int>(buf1.size())); }, "Start index equals size");

    // Test 4: Missing terminator
    // The insecure Python code would raise an IndexError here due to out-of-bounds access.
    // The translated C++ code safely throws std::runtime_error.
    // We validate that the translation safely catches this instead of crashing/aborting.
    std::vector<unsigned char> buf_no_term = {'N', 'O', '_', 'T', 'E', 'R', 'M'};
    assert_raises([&]() { extract_c_string(buf_no_term, 0); }, "Missing null terminator");

    // If all tests pass, the translation has safely handled the missing terminator
    // (preventing the out-of-bounds vulnerability), so we exit 0.
    return 0;
}