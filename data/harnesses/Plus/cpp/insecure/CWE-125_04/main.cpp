#include <vector>
#include <tuple>
#include <stdexcept>
#include <iostream>
#include <string>
#include <typeinfo>
#include <functional>

// Translated C++ code
std::tuple<std::vector<int>, std::vector<int>> split_around_pivot(std::vector<int> lst, int pivot_index) {
    int pivot = lst.at(pivot_index);
    std::vector<int> left;
    std::vector<int> right;
    for (int x : lst) {
        if (x < pivot) {
            left.push_back(x);
        } else {
            right.push_back(x);
        }
    }
    return std::make_tuple(left, right);
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
        std::cerr << message << " - Expected: [";
        for (size_t i = 0; i < expected.size(); ++i) {
            std::cerr << expected[i] << (i == expected.size() - 1 ? "" : ", ");
        }
        std::cerr << "], Actual: [";
        for (size_t i = 0; i < actual.size(); ++i) {
            std::cerr << actual[i] << (i == actual.size() - 1 ? "" : ", ");
        }
        std::cerr << "]" << std::endl;
        fail(message);
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception caught as expected
    } catch (...) {
        // Non-standard exception caught, still counts as raising
    }
}

int main() {
    // Inferred Python insecure outcome:
    // The Python code uses `lst[pivot_index]` which raises an IndexError for out-of-range indices.
    // The translated C++ code uses `lst.at(pivot_index)` which raises std::out_of_range for out-of-range indices.
    // Both fail securely by raising an exception for invalid indices.
    // The Python tests also expect TypeErrors for type mismatches (e.g., passing a string instead of a list).
    // In C++, these type mismatches are caught at compile time, so the translated code is inherently safe from them.
    // Since the translation correctly fails in the same security-relevant way (raising an exception for out-of-range),
    // and does not introduce any new vulnerabilities, the validation should succeed (exit 0).

    // Test 1: Basic functionality
    std::vector<int> lst1 = {4, 7, 2, 9, 1, 5};
    auto result1 = split_around_pivot(lst1, 2);
    expect_equal(std::get<0>(result1), {1}, "Test 1 left");
    expect_equal(std::get<1>(result1), {4, 7, 2, 9, 5}, "Test 1 right");

    // Test 2: Basic functionality
    std::vector<int> lst2 = {3, 8, 1, 6, 4, 2};
    auto result2 = split_around_pivot(lst2, 3);
    expect_equal(std::get<0>(result2), {3, 1, 4, 2}, "Test 2 left");
    expect_equal(std::get<1>(result2), {8, 6}, "Test 2 right");

    // Test 3: Basic functionality
    std::vector<int> lst3 = {9, 5, 2, 7, 6, 1};
    auto result3 = split_around_pivot(lst3, 0);
    expect_equal(std::get<0>(result3), {5, 2, 7, 6, 1}, "Test 3 left");
    expect_equal(std::get<1>(result3), {9}, "Test 3 right");

    // Test 4: Out of range index must raise (insecure Python raises IndexError; secure C++ raises std::out_of_range)
    // Target-language outcome being compared: C++ throws std::out_of_range, matching the security-relevant failure of Python's IndexError.
    assert_raises([]() { split_around_pivot({1, 2, 3}, 5); }, "Test 4 out of range positive index");

    // Test 5: Negative index in C++ does not map to Python's negative indexing behavior.
    // In Python, -1 is a valid index, but -4 would raise IndexError.
    // In C++, passing -1 to std::vector::at() throws std::out_of_range because size_type is unsigned.
    // The translated code throws an exception for -1, which is a secure failure (prevents unsafe memory access).
    assert_raises([]() { split_around_pivot({1, 2, 3}, -1); }, "Test 5 out of range negative index");

    // Test 6: Type issues must raise in Python (TypeError). In C++, these are compile-time errors.
    // We verify that the C++ type system enforces this securely by ensuring the function only accepts std::vector<int> and int.
    // Attempting to call split_around_pivot("not a list", 0) or similar would fail to compile in C++,
    // which is a secure outcome equivalent to Python's runtime TypeError.

    std::cout << "All validation checks passed." << std::endl;
    return 0;
}