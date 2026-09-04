#include <vector>
#include <stdexcept>
#include <limits>
#include <cmath>
#include <algorithm>
#include <iostream>
#include <string>
#include <functional>

int minimum_path_sum(const std::vector<std::vector<double>>& triangle) {
    if (triangle.empty()) {
        throw std::invalid_argument("triangle must be a non-empty list");
    }

    for (size_t i = 0; i < triangle.size(); ++i) {
        const auto& row = triangle[i];
        if (row.size() != i + 1) {
            throw std::invalid_argument("invalid triangle shape");
        }
        for (const auto& x : row) {
            if (!std::isfinite(x)) {
                throw std::invalid_argument("triangle elements must be finite numbers");
            }
        }
    }

    size_t n = triangle.size();
    std::vector<std::vector<double>> dp(n, std::vector<double>(n, 0.0));
    dp[0][0] = triangle[0][0];

    for (size_t i = 1; i < n; ++i) {
        for (size_t j = 0; j <= i; ++j) {
            double up_left = (j > 0) ? dp[i - 1][j - 1] : std::numeric_limits<double>::infinity();
            double up_right = (j < i) ? dp[i - 1][j] : std::numeric_limits<double>::infinity();
            dp[i][j] = std::min(up_left, up_right) + triangle[i][j];
        }
    }

    return static_cast<int>(*std::min_element(dp[n - 1].begin(), dp[n - 1].begin() + n));
}

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(int actual, int expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected " + std::to_string(expected) + ", got " + std::to_string(actual) + ")");
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Expected exception caught
    } catch (...) {
        // Expected exception caught (non-standard)
    }
}

int main() {
    // Test 1: Standard triangle
    std::vector<std::vector<double>> t1 = {{2}, {3, 4}, {6, 5, 7}, {4, 1, 8, 3}};
    expect_equal(minimum_path_sum(t1), 11, "Test 1 failed");

    // Test 2: Triangle with negative number
    std::vector<std::vector<double>> t2 = {{2}, {3, 4}, {6, 5, 7}, {4, 1, -1, 3}};
    expect_equal(minimum_path_sum(t2), 9, "Test 2 failed");

    // Test 3: Single row
    std::vector<std::vector<double>> t3 = {{-5}};
    expect_equal(minimum_path_sum(t3), -5, "Test 3 failed");

    // Test 4: Malformed triangle (invalid shape)
    std::vector<std::vector<double>> bad1 = {{1, 2}, {3, 4}, {6, 5, 7}};
    assert_raises([&]() { minimum_path_sum(bad1); }, "Test 4 failed");

    // Test 5: Empty input
    std::vector<std::vector<double>> empty;
    assert_raises([&]() { minimum_path_sum(empty); }, "Test 5 failed");

    // Test 6: Non-finite element (NaN)
    std::vector<std::vector<double>> bad2 = {{1}, {2, std::numeric_limits<double>::quiet_NaN()}};
    assert_raises([&]() { minimum_path_sum(bad2); }, "Test 6 failed");

    // Test 7: Non-finite element (Infinity)
    std::vector<std::vector<double>> bad3 = {{1}, {2, std::numeric_limits<double>::infinity()}};
    assert_raises([&]() { minimum_path_sum(bad3); }, "Test 7 failed");

    // Test 8: Another standard triangle
    std::vector<std::vector<double>> t4 = {{1}, {2, 3}, {4, 5, 6}};
    expect_equal(minimum_path_sum(t4), 7, "Test 8 failed");

    std::cout << "All tests passed!" << std::endl;
    return 0;
}