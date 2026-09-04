#include <vector>
#include <stdexcept>
#include <string>
#include <iostream>
#include <functional>

// Translated function
std::vector<int> write_values_at_positions(std::vector<int> buffer, const std::vector<int>& positions, const std::vector<int>& values) {
    if (positions.size() != values.size()) {
        throw std::invalid_argument("positions and values must have the same length");
    }

    std::size_t n = buffer.size();

    // Validate all indices first (avoid partial modification)
    for (int p : positions) {
        if (p < 0 || static_cast<std::size_t>(p) >= n) {
            throw std::out_of_range("position out of range");
        }
    }

    for (std::size_t i = 0; i < positions.size(); ++i) {
        buffer[positions[i]] = values[i];
    }

    return buffer;
}

// Test helpers
int test_failures = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    ++test_failures;
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

void assert_raises(const std::function<std::vector<int>()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception caught as expected
    }
}

// Check function equivalent to the Python tests
void check() {
    // normal writes
    expect_equal(write_values_at_positions({0, 0, 0, 0}, {1, 3}, {9, 7}), {0, 9, 0, 7}, "normal writes 1");
    expect_equal(write_values_at_positions({5}, {0}, {6}), {6}, "normal writes 2");
    expect_equal(write_values_at_positions({1, 2, 3}, {}, {}), {1, 2, 3}, "normal writes 3");

    // mismatched lengths
    assert_raises([]() { return write_values_at_positions({0, 0}, {0}, {1, 2}); }, "mismatched lengths");

    // out-of-range indices
    assert_raises([]() { return write_values_at_positions({0, 0, 0}, {3}, {1}); }, "out-of-range index 3");
    assert_raises([]() { return write_values_at_positions({0, 0, 0}, {-1}, {1}); }, "out-of-range index -1");
}

int main() {
    check();
    if (test_failures > 0) {
        std::cerr << test_failures << " test(s) failed." << std::endl;
        return 1;
    }
    std::cout << "All tests passed." << std::endl;
    return 0;
}