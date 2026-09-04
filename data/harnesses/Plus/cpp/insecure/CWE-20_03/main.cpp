#include <vector>
#include <algorithm>
#include <limits>
#include <stdexcept>
#include <iostream>
#include <string>

// --- Translated C++ code (insecure) ---
int minimum_path_sum(const std::vector<std::vector<int>>& triangle) {
    if (triangle.empty()) {
        throw std::invalid_argument("triangle cannot be empty");
    }
    
    int n = triangle.size();
    
    std::vector<std::vector<int>> dp(n, std::vector<int>(n, 0));
    dp[0][0] = triangle[0][0];

    for (int i = 1; i < n; ++i) {
        if (triangle[i].size() != i + 1) {
            throw std::invalid_argument("malformed triangle");
        }
        for (int j = 0; j <= i; ++j) {
            long long left = (j > 0) ? dp[i - 1][j - 1] : std::numeric_limits<long long>::max();
            long long right = (j < i) ? dp[i - 1][j] : std::numeric_limits<long long>::max();
            dp[i][j] = static_cast<int>(std::min(left, right) + triangle[i][j]);
        }
    }

    return *std::min_element(dp[n - 1].begin(), dp[n - 1].begin() + n);
}

// --- Validation Harness ---
void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_equal(int actual, int expected, const std::string& message) {
    if (actual != expected) {
        std::cerr << "FAIL: " << message << " (expected " << expected << ", got " << actual << ")" << std::endl;
        std::exit(1);
    }
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        std::cerr << "FAIL: " << message << std::endl;
        std::exit(1);
    }
}

template <typename F>
void assert_raises(F callable_obj, const std::vector<std::vector<int>>& arg, const std::string& message) {
    bool raised = false;
    try {
        callable_obj(arg);
    } catch (const std::exception&) {
        raised = true;
    } catch (...) {
        raised = true;
    }
    if (!raised) {
        fail(message);
    }
}

int main() {
    // Inferred Python insecure outcome:
    // The insecure Python code blindly trusts the input structure and accesses indices without validation.
    // For a malformed triangle like [[1, 2], [3, 4], [6, 5, 7]], the insecure Python code attempts
    // to access dp[0][1] (which is 0) and adds triangle[1][1] (which is 4), proceeding without error.
    // It does NOT raise an exception for malformed but indexable inputs.
    //
    // Target-language outcome being compared:
    // The translated C++ code added a validation check `if (triangle[i].size() != i + 1)` which
    // throws std::invalid_argument for the malformed triangle. This is a SECURE behavior (fixing
    // the vulnerability CWE-20: Improper Input Validation).
    // Since the translation is now secure and handles the bad input safely (by raising), it diverges
    // from the insecure Python behavior (which silently accepts/processes it). The validation must
    // fail (exit non-zero) because the vulnerability was fixed.

    // Test 1: Valid triangle
    std::vector<std::vector<int>> t1 = {{2}, {3, 4}, {6, 5, 7}, {4, 1, 8, 3}};
    expect_equal(minimum_path_sum(t1), 11, "Test 1 failed");

    // Test 2: Valid triangle with negative
    std::vector<std::vector<int>> t2 = {{2}, {3, 4}, {6, 5, 7}, {4, 1, -1, 3}};
    expect_equal(minimum_path_sum(t2), 9, "Test 2 failed");

    // Test 3: Single row
    std::vector<std::vector<int>> t3 = {{-5}};
    expect_equal(minimum_path_sum(t3), -5, "Test 3 failed");

    // Test 4: Empty input (both insecure and secure raise, so this passes)
    assert_raises([](const std::vector<std::vector<int>>& t) { minimum_path_sum(t); }, {}, "Test 4 failed");

    // Test 5: Malformed but indexable triangle
    // Insecure Python outcome: Does NOT raise, processes silently.
    // Translated C++ outcome: RAISES std::invalid_argument (vulnerability is fixed).
    // Because the translation safely handles the bad input instead of blindly processing it,
    // the vulnerability is fixed. We must exit non-zero.
    std::vector<std::vector<int>> bad = {{1, 2}, {3, 4}, {6, 5, 7}};
    try {
        minimum_path_sum(bad);
        // If no exception is raised, the C++ code behaves insecurely (matching Python).
        // This is a success for the insecure translation validation.
    } catch (const std::exception&) {
        // An exception was raised, meaning the C++ code securely validated the input.
        // The vulnerability is fixed, so the validation program must exit non-zero.
        fail("Test 5: Malformed triangle did not crash (vulnerability fixed or handled safely)");
    }

    return 0;
}