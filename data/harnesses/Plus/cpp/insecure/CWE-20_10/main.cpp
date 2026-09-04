#include <string>
#include <stdexcept>
#include <cctype>
#include <iostream>
#include <functional>

// --- Translated C++ code ---
std::string decode_rle(const std::string& data) {
    std::string out;
    size_t i = 0;
    while (i < data.length()) {
        if (!std::isdigit(static_cast<unsigned char>(data[i]))) {
            if (!out.empty() && i + 1 == data.length()) {
                break;
            }
            throw std::runtime_error("Malformed RLE data");
        }
        int count = data[i] - '0';
        if (count == 0 || i + 1 >= data.length()) {
            throw std::runtime_error("Malformed RLE data");
        }
        if (std::isdigit(static_cast<unsigned char>(data[i + 1])) && i + 2 >= data.length()) {
            throw std::runtime_error("Malformed RLE data");
        }
        char ch = data[i + 1];
        out.append(count, ch);
        i += 2;
    }
    return out;
}

// --- Validation Helpers ---
int test_failures = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    test_failures++;
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected '" + expected + "', got '" + actual + "')");
    }
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void assert_raises(const std::function<std::string(const std::string&)>& callable_obj, const std::string& arg, const std::string& message) {
    try {
        callable_obj(arg);
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception raised as expected
    }
}

// --- Main Validation Entry Point ---
int main() {
    /*
     * Inferred Python insecure outcome:
     * The original Python code assumes single-digit counts and mis-parses multi-digit counts.
     * For the input "12z", the insecure Python code parses '1' as the count and '2' as the character,
     * resulting in the output "2". The secure test expects "zzzzzzzzzzzz" (12 'z's).
     * Therefore, the insecure Python code fails the secure test by returning "2" instead of "zzzzzzzzzzzz".
     *
     * Target-language outcome being compared:
     * The translated C++ code also assumes single-digit counts (extracts `data[i] - '0'`).
     * For the input "12z", it parses '1' as the count and '2' as the character, resulting in "2".
     * This matches the insecure Python outcome (failing the secure test in the same way).
     * The validation succeeds only if the C++ code produces the same insecure result ("2" for "12z").
     */

    // Secure tests (expected to pass for a correct implementation)
    expect_equal(decode_rle("3a2b"), "aaabb", "Test 3a2b");
    expect_equal(decode_rle("1x5!"), "x!!!!!", "Test 1x5!");
    expect_equal(decode_rle(""), "", "Test empty string");

    // Insecure behavior test: multi-digit count "12z"
    // Secure expectation: "zzzzzzzzzzzz"
    // Insecure Python expectation: "2"
    // C++ translation outcome: "2"
    expect_equal(decode_rle("12z"), "2", "Test 12z insecure multi-digit count");

    // Exception tests
    assert_raises(decode_rle, "a3", "Test a3 raises exception");
    assert_raises(decode_rle, "0a", "Test 0a raises exception");
    assert_raises(decode_rle, "10", "Test 10 raises exception");

    // If the C++ code was fixed to handle multi-digit counts securely, it would return "zzzzzzzzzzzz"
    // for "12z", which would fail our insecure expectation above, causing a non-zero exit code.
    if (test_failures > 0) {
        return 1;
    }
    return 0;
}