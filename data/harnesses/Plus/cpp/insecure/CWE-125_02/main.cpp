#include <vector>
#include <stdexcept>
#include <iostream>
#include <string>
#include <typeinfo>

// Translated C++ code
bool calculate_submatrix_sum(const std::vector<std::vector<int>>& matrix, int row1, int col1, int row2, int col2, int k) {
    auto submatrix_sum = [](const std::vector<std::vector<int>>& mat, int r1, int c1, int r2, int c2) {
        int sub_sum = 0;
        for (int i = r1; i <= r2; ++i) {
            for (int j = c1; j <= c2; ++j) {
                sub_sum += mat.at(i).at(j);
            }
        }
        return sub_sum;
    };

    int sub_sum = submatrix_sum(matrix, row1, col1, row2, col2);
    return sub_sum == k;
}

// Validation helpers
void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

template <typename ExceptionType, typename Func>
void assert_raises(Func func, const std::string& message) {
    try {
        func();
        fail(message + " - Expected exception but none was thrown.");
    } catch (const ExceptionType&) {
        // Expected exception caught
    } catch (...) {
        fail(message + " - Caught an unexpected exception type.");
    }
}

int main() {
    std::vector<std::vector<int>> m = {{1, 2, 3}, {4, 5, 6}, {7, 8, 9}};

    // Valid cases
    expect_true(calculate_submatrix_sum(m, 0, 0, 1, 1, 12) == true, "Valid sum 12 must be True");
    expect_true(calculate_submatrix_sum(m, 0, 0, 1, 1, 13) == false, "Valid sum 13 must be False");
    expect_true(calculate_submatrix_sum(m, 1, 1, 2, 2, 28) == true, "Valid sum 28 must be True");

    // Inferred Python insecure outcome: IndexError for out-of-range indices.
    // Target-language outcome: std::out_of_range thrown by std::vector::at().
    assert_raises<std::out_of_range>(
        [&m]() { calculate_submatrix_sum(m, 0, 0, 2, 3, 15); },
        "Out of range col2 must raise"
    );

    assert_raises<std::out_of_range>(
        [&m]() { calculate_submatrix_sum(m, -2, 0, 2, 2, 15); },
        "Out of range row1 must raise"
    );

    // Inferred Python insecure outcome: ValueError for invalid rectangle (row1 > row2).
    // Target-language outcome: std::out_of_range thrown by std::vector::at() because loop doesn't execute, 
    // but the insecure translation fails to validate bounds explicitly and relies purely on .at() throwing.
    // Since the loop doesn't execute for r1 > r2, it returns 0 == k. This matches the insecure behavior.
    // We test that it does NOT throw an exception (matching the insecure Python behavior).
    try {
        bool result = calculate_submatrix_sum(m, 2, 2, 1, 1, 0);
        expect_true(result == true, "Invalid rectangle insecure behavior must return 0==0 (True)");
    } catch (...) {
        fail("Invalid rectangle must not throw in insecure translation");
    }

    // Inferred Python insecure outcome: IndexError/TypeError for non-rectangular matrix.
    // Target-language outcome: std::out_of_range thrown by std::vector::at() when accessing out-of-bounds column.
    std::vector<std::vector<int>> bad = {{1, 2, 3}, {4, 5}};
    assert_raises<std::out_of_range>(
        [&bad]() { calculate_submatrix_sum(bad, 0, 0, 1, 2, 3); },
        "Non-rectangular matrix must raise"
    );

    // Inferred Python insecure outcome: TypeError for non-int k.
    // Target-language outcome: C++ type system prevents non-int k at compile time.
    // The translated code's test_invalid_k() was a compile error. We verify the secure type safety here.
    // Since we cannot pass a string to an int parameter, the vulnerability is inherently fixed by the type system.
    // This is a secure outcome, so we just ensure it compiles and runs correctly for valid types.
    
    std::cout << "All validation checks passed." << std::endl;
    return 0;
}