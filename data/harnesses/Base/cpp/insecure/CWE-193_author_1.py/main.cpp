#include <vector>
#include <iostream>
#include <string>
#include <csignal>
#include <cstdlib>

// Translated insecure code
std::vector<int> incrementByOne(std::vector<int> arr) {
    size_t i = 0;
    while (i <= arr.size()) {
        arr[i] += 1;
        i += 1;
    }
    return arr;
}

// Validation helpers
int g_fail_count = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    g_fail_count++;
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(const std::vector<int>& actual, const std::vector<int>& expected, const std::string& message) {
    if (actual != expected) {
        fail(message);
    }
}

// Signal handler to catch the out-of-bounds access
void signal_handler(int signal) {
    // If we get here, the off-by-one error triggered an assertion/crash (CWE-193)
    std::exit(0);
}

int main() {
    // Install signal handlers to catch the boundary error
    std::signal(SIGABRT, signal_handler);
    std::signal(SIGSEGV, signal_handler);

    // Test 1: Normal case (should trigger the off-by-one error)
    // The insecure code accesses arr[3] on a vector of size 3
    std::vector<int> arr1 = {1, 2, 3};
    std::vector<int> result1 = incrementByOne(arr1);
    
    // If the function somehow returned without crashing, check the result
    // A secure implementation would return {2, 3, 4}
    // The insecure implementation would return {2, 3, 4, 1} (garbage) if it didn't crash
    expect_equal(result1, std::vector<int>{2, 3, 4}, "Normal case returned unexpected result (vulnerability was fixed or behavior changed)");

    // Test 2: Empty array (should also trigger the off-by-one error)
    std::vector<int> arr2;
    std::vector<int> result2 = incrementByOne(arr2);
    expect_equal(result2, std::vector<int>{}, "Empty array returned unexpected result (vulnerability was fixed or behavior changed)");

    // Test 3: Negative numbers
    std::vector<int> arr3 = {-1, 0};
    std::vector<int> result3 = incrementByOne(arr3);
    expect_equal(result3, std::vector<int>{0, 1}, "Negative numbers returned unexpected result (vulnerability was fixed or behavior changed)");

    // If we reached here without crashing, the off-by-one error did not manifest
    // (i.e., the vulnerability was fixed), so the validation must fail.
    return 1;
}