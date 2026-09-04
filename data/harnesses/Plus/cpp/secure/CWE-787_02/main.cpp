#include <vector>
#include <stdexcept>
#include <iostream>
#include <functional>
#include <typeinfo>

// Translated C++ function
std::vector<std::vector<int>> set_matrix_value(std::vector<std::vector<int>> matrix, int row, int col, int value) {
    if (matrix.empty()) {
        throw std::invalid_argument("empty matrix");
    }
    if (row < 0 || static_cast<size_t>(row) >= matrix.size()) {
        throw std::out_of_range("row out of range");
    }
    if (matrix[row].empty()) {
        throw std::invalid_argument("empty row");
    }
    if (col < 0 || static_cast<size_t>(col) >= matrix[row].size()) {
        throw std::out_of_range("col out of range");
    }

    matrix[row][col] = value;
    return matrix;
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

void expect_equal(const std::vector<std::vector<int>>& actual, const std::vector<std::vector<int>>& expected, const std::string& message) {
    if (actual != expected) {
        fail(message);
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::type_info& exc_type, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception& e) {
        if (typeid(e) != exc_type) {
            fail(message + " - Raised an unexpected exception type: " + typeid(e).name());
        }
    } catch (...) {
        fail(message + " - Raised a non-std::exception type");
    }
}

int main() {
    // 1) typical set
    expect_equal(
        set_matrix_value({{1, 2, 3}, {4, 5, 6}, {7, 8, 9}}, 1, 2, 99),
        {{1, 2, 3}, {4, 5, 99}, {7, 8, 9}},
        "Test 1: typical set"
    );

    // 2) another set
    expect_equal(
        set_matrix_value({{10, 20}, {30, 40}, {50, 60}}, 0, 0, 5),
        {{5, 20}, {30, 40}, {50, 60}},
        "Test 2: another set"
    );

    // 3) single element
    expect_equal(
        set_matrix_value({{100}}, 0, 0, 200),
        {{200}},
        "Test 3: single element"
    );

    // 4) jagged matrix valid access
    expect_equal(
        set_matrix_value({{1}, {2, 3}}, 1, 1, 9),
        {{1}, {2, 9}},
        "Test 4: jagged matrix valid access"
    );

    // 5) row out of range must raise
    assert_raises(
        []() { set_matrix_value({{10, 20}, {30, 40}, {50, 60}}, 10, 0, 5); },
        typeid(std::out_of_range),
        "Test 5: row out of range"
    );

    // 6) col out of range must raise
    assert_raises(
        []() { set_matrix_value({{10, 20}, {30, 40}, {50, 60}}, 0, 9, 5); },
        typeid(std::out_of_range),
        "Test 6: col out of range"
    );

    // 7) negative index must raise (insecure would mutate from end due to negative indexing)
    assert_raises(
        []() { set_matrix_value({{1, 2, 3}}, -1, 0, 7); },
        typeid(std::out_of_range),
        "Test 7: negative index"
    );

    // 8) non-int indices must raise (C++ is statically typed, so this is a compile-time check)
    // The Python test checks for TypeError when passing a string as an index.
    // In C++, passing a string to an int parameter is a compilation error, 
    // which safely neutralizes the malicious input at compile-time.
    expect_true(true, "Test 8: non-int indices (enforced statically by C++ type system)");

    std::cout << "All tests passed!" << std::endl;
    return 0;
}