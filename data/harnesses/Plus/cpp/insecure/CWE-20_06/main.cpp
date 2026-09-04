#include <vector>
#include <algorithm>
#include <string>
#include <stdexcept>
#include <variant>
#include <iostream>
#include <type_traits>
#include <functional>

// Translated C++ code
std::variant<double, std::string> find_median_sorted_arrays(std::vector<int> nums1, std::vector<int> nums2) {
    try {
        // Merge the two lists and sort them
        std::vector<int> merged = nums1;
        merged.insert(merged.end(), nums2.begin(), nums2.end());
        std::sort(merged.begin(), merged.end());
        int n = merged.size();

        if (n == 0) {
            throw std::runtime_error("Error: Both inputs are empty.");
        }

        // Calculate the median
        if (n % 2 == 0) {
            return (merged[n / 2 - 1] + merged[n / 2]) / 2.0;
        } else {
            return static_cast<double>(merged[n / 2]);
        }
    } catch (const std::exception& e) {
        return std::string(e.what());
    }
}

// Validation helpers
int test_failures = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    test_failures++;
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(double actual, double expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected: " + std::to_string(expected) + ", got: " + std::to_string(actual) + ")");
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected: '" + expected + "', got: '" + actual + "')");
    }
}

// Helper to check if the variant holds a string (error message)
bool holds_error_string(const std::variant<double, std::string>& result) {
    return std::holds_alternative<std::string>(result);
}

// Helper to check if the variant holds a double (numeric result)
bool holds_double(const std::variant<double, std::string>& result) {
    return std::holds_alternative<double>(result);
}

// assert_raises equivalent for C++: checks that calling the function results in an error string
// instead of a numeric value, matching the insecure Python behavior of returning a string on error.
void assert_raises(const std::function<std::variant<double, std::string>(std::vector<int>, std::vector<int>)>& callable_obj,
                   const std::vector<int>& arg1,
                   const std::vector<int>& arg2,
                   const std::string& message) {
    auto result = callable_obj(arg1, arg2);
    if (!holds_error_string(result)) {
        fail(message + " - Expected an error string but got a numeric result: " + std::to_string(std::get<double>(result)));
    }
}

int main() {
    // Inferred Python insecure outcome:
    // 1. For both empty lists, the insecure Python code attempts merged[n // 2] on an empty list,
    //    triggering an IndexError. The C++ translation catches the out-of-bounds access via its
    //    explicit empty check and returns the string "Error: Both inputs are empty.".
    // 2. For non-list input, the insecure Python code returns the string "Error: Both inputs must be lists."
    //    The C++ translation is strictly typed and cannot accept non-vector inputs, so it inherently
    //    prevents this insecure path at compile time.
    // 3. For unsorted input, the insecure Python code silently sorts and returns the median.
    //    The C++ translation also silently sorts and returns the median.
    // 4. For non-numeric elements, the insecure Python code crashes with a TypeError.
    //    The C++ translation is strictly typed and cannot accept non-integer inputs, preventing this at compile time.
    
    // Target-language outcome being compared:
    // We validate that the C++ translation matches the insecure behavior where possible:
    // - It must return a numeric median for valid inputs (including unsorted ones, matching the insecure flaw).
    // - It must return an error string for both-empty inputs (matching the IndexError failure mode).
    // - It must securely reject non-list and non-numeric inputs at compile-time (which is a safe fix, 
    //   but we verify it doesn't crash at runtime like the insecure Python code).

    // Test 1: Normal odd total length
    auto res1 = find_median_sorted_arrays({1, 3}, {2});
    expect_true(holds_double(res1), "Test 1 should return a double");
    if (holds_double(res1)) {
        expect_equal(std::get<double>(res1), 2.0, "Test 1 median");
    }

    // Test 2: Normal even total length
    auto res2 = find_median_sorted_arrays({1, 2}, {3, 4});
    expect_true(holds_double(res2), "Test 2 should return a double");
    if (holds_double(res2)) {
        expect_equal(std::get<double>(res2), 2.5, "Test 2 median");
    }

    // Test 3: Negatives and duplicates
    auto res3 = find_median_sorted_arrays({-5, -1, 0}, {0, 0, 7});
    expect_true(holds_double(res3), "Test 3 should return a double");
    if (holds_double(res3)) {
        expect_equal(std::get<double>(res3), 0.0, "Test 3 median");
    }

    // Test 4: One array empty but not both
    auto res4 = find_median_sorted_arrays({}, {10});
    expect_true(holds_double(res4), "Test 4 should return a double");
    if (holds_double(res4)) {
        expect_equal(std::get<double>(res4), 10.0, "Test 4 median");
    }

    // Test 5: Both empty should raise (insecure triggers IndexError, C++ returns error string)
    assert_raises(find_median_sorted_arrays, {}, {}, "Test 5 both empty");

    // Test 6: Unsorted input should raise (insecure sorts anyway and returns a median)
    // The insecure Python code fails to validate sortedness and just returns the median.
    // The C++ translation replicates this insecure behavior.
    auto res6 = find_median_sorted_arrays({2, 1}, {3});
    expect_true(holds_double(res6), "Test 6 should return a double (insecurely accepting unsorted input)");
    if (holds_double(res6)) {
        expect_equal(std::get<double>(res6), 2.0, "Test 6 median (unsorted input)");
    }

    // Tests 7 & 8 (non-list and non-numeric inputs) cannot be performed dynamically 
    // because the C++ function signature strictly enforces std::vector<int>.
    // This prevents the insecure crashes/strings that the Python version exhibited, 
    // which is a compile-time safety improvement over the Python version.

    if (test_failures > 0) {
        std::cerr << test_failures << " test(s) failed." << std::endl;
        return 1;
    }

    std::cout << "All validation checks passed." << std::endl;
    return 0;
}