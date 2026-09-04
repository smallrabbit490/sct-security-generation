#include <vector>
#include <stdexcept>
#include <type_traits>
#include <algorithm>
#include <iostream>
#include <cmath>
#include <string>
#include <functional>

double find_median_sorted_arrays(const std::vector<double>& nums1, const std::vector<double>& nums2) {
    std::vector<double> merged;
    merged.reserve(nums1.size() + nums2.size());
    merged.insert(merged.end(), nums1.begin(), nums1.end());
    merged.insert(merged.end(), nums2.begin(), nums2.end());

    if (merged.empty()) {
        throw std::invalid_argument("both arrays are empty");
    }

    for (double x : merged) {
        if (!std::isfinite(x)) {
            throw std::invalid_argument("all elements must be finite numbers");
        }
    }

    for (const auto& arr : {nums1, nums2}) {
        for (size_t i = 1; i < arr.size(); ++i) {
            if (arr[i] < arr[i - 1]) {
                throw std::invalid_argument("inputs must be sorted");
            }
        }
    }

    std::sort(merged.begin(), merged.end());

    size_t n = merged.size();
    if (n % 2 == 1) {
        return merged[n / 2];
    }
    return (merged[n / 2 - 1] + merged[n / 2]) / 2.0;
}

// Test harness helpers

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(double actual, double expected, const std::string& message) {
    if (std::isnan(actual) || std::isnan(expected) || std::abs(actual - expected) > 1e-9) {
        std::cerr << "FAIL: " << message << " (expected " << expected << ", got " << actual << ")" << std::endl;
        std::exit(1);
    }
}

void assert_raises(const std::function<double()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception caught as expected
    } catch (...) {
        // Non-standard exception caught, also acceptable
    }
}

int main() {
    // Test 1: Basic odd total length
    expect_equal(find_median_sorted_arrays({1, 3}, {2}), 2.0, "Test 1: [1, 3] and [2]");

    // Test 2: Basic even total length
    expect_equal(find_median_sorted_arrays({1, 2}, {3, 4}), 2.5, "Test 2: [1, 2] and [3, 4]");

    // Test 3: Negatives and duplicates
    expect_equal(find_median_sorted_arrays({-5, -1, 0}, {0, 0, 7}), 0.0, "Test 3: [-5, -1, 0] and [0, 0, 7]");

    // Test 4: One array empty but not both
    expect_equal(find_median_sorted_arrays({}, {10}), 10.0, "Test 4: [] and [10]");

    // Test 5: Both empty should raise
    assert_raises([]() { return find_median_sorted_arrays({}, {}); }, "Test 5: both arrays empty");

    // Test 6: Unsorted input should raise
    assert_raises([]() { return find_median_sorted_arrays({2, 1}, {3}); }, "Test 6: unsorted input");

    // Test 7: Non-finite element (NaN) should raise
    assert_raises([]() { return find_median_sorted_arrays({1, std::nan("")}, {2}); }, "Test 7: NaN element");

    // Test 8: Non-finite element (Infinity) should raise
    assert_raises([]() { return find_median_sorted_arrays({1, INFINITY}, {2}); }, "Test 8: Infinity element");

    std::cout << "All tests passed!" << std::endl;
    return 0;
}