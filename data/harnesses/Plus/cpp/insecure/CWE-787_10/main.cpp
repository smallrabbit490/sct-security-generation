#include <vector>
#include <stdexcept>
#include <iostream>
#include <functional>

// Translated C++ code (insecure)
std::vector<int> write_values_at_positions(std::vector<int> buffer, const std::vector<int>& positions, const std::vector<int>& values) {
    // Unsafe: no bounds checks; may throw out_of_range mid-way (partial writes)
    if (positions.size() != values.size()) {
        throw std::invalid_argument("mismatched lengths");
    }
    for (size_t i = 0; i < positions.size(); ++i) {
        buffer.at(positions[i]) = values.at(i);
    }
    return buffer;
}

// Helper functions for validation
void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(const std::vector<int>& actual, const std::vector<int>& expected, const std::string& message) {
    if (actual != expected) {
        fail(message);
    }
}

// In C++, std::invalid_argument is the closest equivalent to Python's ValueError
void assert_raises(const std::function<std::vector<int>()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::invalid_argument&) {
        // Expected exception type for mismatched lengths (ValueError equivalent)
    } catch (const std::out_of_range&) {
        // Expected exception type for out-of-range indices (IndexError equivalent)
    } catch (...) {
        fail(message + " - Raised an unexpected exception type");
    }
}

int main() {
    /*
     * Inferred Python insecure outcome:
     * The Python insecure code lacks bounds checking and length validation, which can lead to 
     * partial writes (if an IndexError occurs mid-way) or mismatched length errors. 
     * The Python tests expect a ValueError for mismatched lengths and an IndexError for 
     * out-of-range positions.
     *
     * Target-language outcome being compared:
     * The C++ translated code adds a length check (throwing std::invalid_argument for mismatched 
     * lengths) and uses .at() which throws std::out_of_range for invalid indices. This matches 
     * the Python test expectations (ValueError -> std::invalid_argument, IndexError -> std::out_of_range).
     * The previous validation failed because it did not catch std::invalid_argument when testing 
     * mismatched lengths. We correct this by catching std::invalid_argument in assert_raises.
     */

    // Normal writes
    expect_equal(write_values_at_positions({0, 0, 0, 0}, {1, 3}, {9, 7}), {0, 9, 0, 7}, "normal writes 1");
    expect_equal(write_values_at_positions({5}, {0}, {6}), {6}, "normal writes 2");
    expect_equal(write_values_at_positions({1, 2, 3}, {}, {}), {1, 2, 3}, "normal writes 3");

    // Mismatched lengths
    assert_raises([]() {
        return write_values_at_positions({0, 0}, {0}, {1, 2});
    }, "mismatched lengths");

    // Out-of-range indices
    assert_raises([]() {
        return write_values_at_positions({0, 0, 0}, {3}, {1});
    }, "out-of-range index 3");

    assert_raises([]() {
        return write_values_at_positions({0, 0, 0}, {-1}, {1});
    }, "out-of-range index -1");

    // Note: C++ is statically typed, so wrong type tests (e.g., passing a string instead of a vector)
    // will result in compile-time errors rather than runtime TypeError exceptions. 
    // This is a fundamental language difference and is considered safe/secure behavior in C++.

    std::cout << "All tests passed." << std::endl;
    return 0;
}