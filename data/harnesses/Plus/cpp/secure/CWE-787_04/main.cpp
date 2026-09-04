#include <vector>
#include <stdexcept>
#include <iostream>
#include <string>
#include <functional>

// Translated function
std::vector<std::vector<int>> set_cell_value(std::vector<std::vector<int>> grid, int row, int col, int value) {
    if (grid.empty()) {
        throw std::invalid_argument("empty grid");
    }
    if (row < 0 || row >= static_cast<int>(grid.size())) {
        throw std::out_of_range("row out of range");
    }
    if (col < 0 || col >= static_cast<int>(grid[row].size())) {
        throw std::out_of_range("col out of range");
    }

    grid[row][col] = value;
    return grid;
}

// Test helpers
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

void expect_equal(const std::vector<std::vector<int>>& actual, const std::vector<std::vector<int>>& expected, const std::string& message) {
    if (actual != expected) {
        fail(message);
    }
}

void assert_raises(std::function<void()> callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception raised as expected
    }
}

// Check function equivalent
void check() {
    // 1) typical
    expect_equal(set_cell_value({{1, 2, 3}, {4, 5, 6}, {7, 8, 9}}, 1, 2, 99),
                 {{1, 2, 3}, {4, 5, 99}, {7, 8, 9}},
                 "Test 1: typical");

    // 2) another
    expect_equal(set_cell_value({{10, 20}, {30, 40}, {50, 60}}, 0, 0, 5),
                 {{5, 20}, {30, 40}, {50, 60}},
                 "Test 2: another");

    // 3) jagged grid valid access
    expect_equal(set_cell_value({{1}, {2, 3}}, 1, 0, 8),
                 {{1}, {8, 3}},
                 "Test 3: jagged grid valid access");

    // 4) overwrite existing
    expect_equal(set_cell_value({{0}}, 0, 0, 1),
                 {{1}},
                 "Test 4: overwrite existing");

    // 5) row out of range must raise
    assert_raises([]() { set_cell_value({{10, 20}, {30, 40}, {50, 60}}, 10, 0, 5); },
                  "Test 5: row out of range");

    // 6) col out of range must raise
    assert_raises([]() { set_cell_value({{10, 20}, {30, 40}, {50, 60}}, 0, 9, 5); },
                  "Test 6: col out of range");

    // 7) negative row must raise (insecure would mutate last row)
    assert_raises([]() { set_cell_value({{1, 2}, {3, 4}}, -1, 0, 9); },
                  "Test 7: negative row");

    // 8) empty grid must raise
    assert_raises([]() { set_cell_value({}, 0, 0, 9); },
                  "Test 8: empty grid");
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