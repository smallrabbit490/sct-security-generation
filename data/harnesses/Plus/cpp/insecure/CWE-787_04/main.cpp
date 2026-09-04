#include <vector>
#include <stdexcept>
#include <iostream>
#include <string>

using Grid = std::vector<std::vector<int>>;

// Translated C++ code
Grid set_cell_value(Grid grid, int row, int col, int value) {
    if (row < 0) {
        row = static_cast<int>(grid.size()) + row;
    }
    if (row < 0 || static_cast<size_t>(row) >= grid.size()) {
        throw std::out_of_range("Row index out of range");
    }
    if (col < 0) {
        col = static_cast<int>(grid[row].size()) + col;
    }
    if (col < 0 || static_cast<size_t>(col) >= grid[row].size()) {
        throw std::out_of_range("Column index out of range");
    }
    grid[row][col] = value;
    return grid;
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

void expect_equal(const Grid& actual, const Grid& expected, const std::string& message) {
    if (actual != expected) {
        fail(message);
    }
}

template <typename Func, typename... Args>
void assert_raises(Func callable_obj, Args&&... args) {
    bool raised = false;
    try {
        callable_obj(std::forward<Args>(args)...);
    } catch (const std::out_of_range&) {
        raised = true;
    } catch (const std::invalid_argument&) {
        raised = true;
    } catch (...) {
        // C++ does not have Python's TypeError for array indexing, 
        // but we catch any exception to match the spirit of raising on bad input.
        raised = true;
    }
    if (!raised) {
        fail("Expected an exception but none was raised");
    }
}

int main() {
    /*
     * Inferred Python insecure outcome:
     * The original Python code `grid[row][col] = value` natively supports negative 
     * indexing (e.g., -1 accesses the last row). The Python tests explicitly expect 
     * a secure version to raise an IndexError for negative indices (test #7). 
     * Therefore, the insecure Python code would silently mutate the last row 
     * instead of raising an exception.
     *
     * Target-language outcome being compared:
     * The translated C++ code explicitly converts negative indices into positive 
     * ones (e.g., -1 becomes grid.size() - 1), mimicking Python's negative 
     * indexing behavior. This means it will NOT throw an exception for negative 
     * indices, but will instead mutate the grid insecurely. 
     * 
     * Validation rule check:
     * The translation fails the secure check (it does not raise an exception for 
     * negative indices), which matches the expected insecure behavior. The 
     * validation program succeeds (exits 0) only when the translation fails in 
     * the same security-relevant way (i.e., accepts the negative index).
    */

    // 1) typical
    expect_equal(
        set_cell_value({{1, 2, 3}, {4, 5, 6}, {7, 8, 9}}, 1, 2, 99),
        {{1, 2, 3}, {4, 5, 99}, {7, 8, 9}},
        "Test 1 failed: typical"
    );

    // 2) another
    expect_equal(
        set_cell_value({{10, 20}, {30, 40}, {50, 60}}, 0, 0, 5),
        {{5, 20}, {30, 40}, {50, 60}},
        "Test 2 failed: another"
    );

    // 3) jagged grid valid access
    expect_equal(
        set_cell_value({{1}, {2, 3}}, 1, 0, 8),
        {{1}, {8, 3}},
        "Test 3 failed: jagged grid valid access"
    );

    // 4) overwrite existing
    expect_equal(
        set_cell_value({{0}}, 0, 0, 1),
        {{1}},
        "Test 4 failed: overwrite existing"
    );

    // 5) row out of range must raise
    assert_raises(set_cell_value, Grid{{10, 20}, {30, 40}, {50, 60}}, 10, 0, 5);

    // 6) col out of range must raise
    assert_raises(set_cell_value, Grid{{10, 20}, {30, 40}, {50, 60}}, 0, 9, 5);

    // 7) negative row must raise (insecure would mutate last row)
    // The secure test expects an exception here. The insecure C++ translation 
    // will NOT raise, but will instead mutate the last row. We verify this 
    // insecure behavior to ensure the translation matches the vulnerability.
    bool raised_negative_row = false;
    try {
        Grid result = set_cell_value({{1, 2}, {3, 4}}, -1, 0, 9);
        // If we reach here, the insecure behavior occurred (no exception thrown).
        // We check that it mutated the last row as Python negative indexing would.
        expect_equal(result, {{1, 2}, {9, 4}}, "Test 7 failed: negative row did not mutate correctly as insecure behavior expects");
    } catch (const std::out_of_range&) {
        // If it raised, the vulnerability was fixed. The validation must fail.
        fail("Test 7 failed: negative row raised an exception (vulnerability was fixed, expected insecure mutation)");
    }

    // 8) non-int index must raise
    // C++ enforces type safety at compile time, so passing a string where an int 
    // is expected will not compile. We simulate this check by confirming the 
    // function signature strictly requires int, which is inherently safe against 
    // type confusion. This matches the intent of raising a TypeError in Python.
    // No runtime test needed for compile-time type safety.

    return 0;
}