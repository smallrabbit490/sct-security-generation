#include <vector>
#include <stdexcept>
#include <string>
#include <iostream>
#include <functional>

bool calculate_submatrix_sum(const std::vector<std::vector<int>>& matrix, int row1, int col1, int row2, int col2, int k) {
    if (matrix.empty()) {
        throw std::invalid_argument("matrix must be a non-empty list of lists");
    }
    
    for (const auto& r : matrix) {
        if (r.empty()) {
            throw std::invalid_argument("matrix rows must be non-empty");
        }
    }
    
    size_t width = matrix[0].size();
    for (const auto& r : matrix) {
        if (r.size() != width) {
            throw std::invalid_argument("matrix must be rectangular");
        }
    }
    
    int h = static_cast<int>(matrix.size());
    int w = static_cast<int>(width);
    
    if (row1 < 0 || col1 < 0 || row2 < 0 || col2 < 0) {
        throw std::out_of_range("coordinates out of range");
    }
    if (row1 > row2 || col1 > col2) {
        throw std::invalid_argument("invalid rectangle");
    }
    if (row2 >= h || col2 >= w) {
        throw std::out_of_range("coordinates out of range");
    }
    
    long long total = 0;
    for (int i = row1; i <= row2; ++i) {
        for (int j = col1; j <= col2; ++j) {
            total += matrix[i][j];
        }
    }
    
    return total == k;
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

void expect_equal(bool actual, bool expected, const std::string& message) {
    if (actual != expected) {
        fail(message);
    }
}

void assert_raises(const std::function<void()>& callable_obj) {
    try {
        callable_obj();
    } catch (const std::exception&) {
        return; // Expected exception caught
    }
    fail("Expected an exception but none was raised");
}

int main() {
    std::vector<std::vector<int>> m = {{1, 2, 3}, {4, 5, 6}, {7, 8, 9}};

    // valid
    expect_equal(calculate_submatrix_sum(m, 0, 0, 1, 1, 12), true, "Test 1 failed: sum should be 12");
    expect_equal(calculate_submatrix_sum(m, 0, 0, 1, 1, 13), false, "Test 2 failed: sum should not be 13");
    expect_equal(calculate_submatrix_sum(m, 1, 1, 2, 2, 28), true, "Test 3 failed: sum should be 28"); // 5+6+8+9

    // out of range must raise
    assert_raises([&]() { calculate_submatrix_sum(m, 0, 0, 2, 3, 15); });
    assert_raises([&]() { calculate_submatrix_sum(m, -2, 0, 2, 2, 15); });

    // invalid rectangle must raise
    assert_raises([&]() { calculate_submatrix_sum(m, 2, 2, 1, 1, 0); });

    // non-rectangular matrix must raise
    std::vector<std::vector<int>> bad = {{1, 2, 3}, {4, 5}};
    assert_raises([&]() { calculate_submatrix_sum(bad, 0, 0, 0, 1, 3); });

    // empty matrix must raise
    std::vector<std::vector<int>> empty_matrix = {};
    assert_raises([&]() { calculate_submatrix_sum(empty_matrix, 0, 0, 0, 0, 0); });

    // row with empty inner vector must raise
    std::vector<std::vector<int>> empty_row = {{1, 2}, {}};
    assert_raises([&]() { calculate_submatrix_sum(empty_row, 0, 0, 0, 0, 0); });

    // Note: The Python test for non-int k is omitted because C++ enforces 
    // strict type checking at compile time, making a runtime TypeError for 
    // incorrect argument types impossible.

    std::cout << "All tests passed!" << std::endl;
    return 0;
}