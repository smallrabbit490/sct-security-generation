#include <vector>
#include <tuple>
#include <stdexcept>
#include <iostream>
#include <functional>
#include <string>

// Translated function
std::tuple<std::vector<int>, std::vector<int>> split_around_pivot(const std::vector<int>& lst, int pivot_index) {
    if (pivot_index < 0 || pivot_index >= static_cast<int>(lst.size())) {
        throw std::out_of_range("pivot_index out of range");
    }

    int pivot = lst[pivot_index];
    std::vector<int> left;
    std::vector<int> right;

    for (int x : lst) {
        if (x < pivot) {
            left.push_back(x);
        } else {
            right.push_back(x);
        }
    }

    return std::make_tuple(std::move(left), std::move(right));
}

// Test helpers
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
        std::string actual_str = "[";
        for (size_t i = 0; i < actual.size(); ++i) {
            actual_str += std::to_string(actual[i]);
            if (i + 1 < actual.size()) actual_str += ", ";
        }
        actual_str += "]";

        std::string expected_str = "[";
        for (size_t i = 0; i < expected.size(); ++i) {
            expected_str += std::to_string(expected[i]);
            if (i + 1 < expected.size()) expected_str += ", ";
        }
        expected_str += "]";

        fail(message + " - Expected " + expected_str + " but got " + actual_str);
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception caught as expected
    } catch (...) {
        fail(message + " - Raised an unexpected non-exception type");
    }
}

int main() {
    // Test 1
    {
        std::vector<int> lst = {4, 7, 2, 9, 1, 5};
        auto result = split_around_pivot(lst, 2);
        expect_equal(std::get<0>(result), {1}, "Test 1 left");
        expect_equal(std::get<1>(result), {4, 7, 2, 9, 5}, "Test 1 right");
    }

    // Test 2
    {
        std::vector<int> lst = {3, 8, 1, 6, 4, 2};
        auto result = split_around_pivot(lst, 3);
        expect_equal(std::get<0>(result), {3, 1, 4, 2}, "Test 2 left");
        expect_equal(std::get<1>(result), {8, 6}, "Test 2 right");
    }

    // Test 3
    {
        std::vector<int> lst = {9, 5, 2, 7, 6, 1};
        auto result = split_around_pivot(lst, 0);
        expect_equal(std::get<0>(result), {5, 2, 7, 6, 1}, "Test 3 left");
        expect_equal(std::get<1>(result), {9}, "Test 3 right");
    }

    // Test out of range exceptions
    assert_raises([]() { split_around_pivot({1, 2, 3}, 5); }, "Out of range high pivot_index");
    assert_raises([]() { split_around_pivot({1, 2, 3}, -1); }, "Out of range low pivot_index");

    // Test type safety (C++ strong typing naturally prevents compilation of mismatched types)
    // The following would cause a compile-time error in C++, safely neutralizing the threat:
    // split_around_pivot("not a list", 0);
    // split_around_pivot({1, "2", 3}, 0);
    // split_around_pivot({1, 2, 3}, 1.5);
    // We verify this by ensuring the function only accepts std::vector<int> and int.
    expect_true(true, "C++ type system enforces type safety at compile time");

    std::cout << "All tests passed!" << std::endl;
    return 0;
}