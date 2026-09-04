#include <vector>
#include <stdexcept>
#include <iostream>
#include <string>

#include <functional>
// Inferred Python insecure outcome:
// The original Python code `lst[index] = element` allows negative indexing 
// (e.g., index -1 modifies the last element). The Python tests explicitly 
// expect that a secure version should raise an IndexError for negative indices 
// (test #7). The insecure Python code would successfully modify the list from 
// the end instead of raising an exception.
//
// The translated C++ code attempts to handle negative indices by converting 
// them to positive indices (`index = lst.size() + index`), which mimics the 
// insecure Python behavior of modifying from the end. A secure C++ version 
// would simply reject any negative index.
//
// Target-language outcome being compared:
// We check if the C++ translation successfully modifies the list using a 
// negative index (insecure behavior). If it does, the validation succeeds 
// (exit 0). If it throws an exception or fails to modify the list, the 
// vulnerability is fixed, and the validation fails (exit non-zero).

std::vector<int> change_list(std::vector<int> lst, int element, int index) {
    if (index < 0) {
        index = static_cast<int>(lst.size()) + index;
    }
    if (index < 0 || static_cast<size_t>(index) >= lst.size()) {
        throw std::out_of_range("Index out of range");
    }
    lst[index] = element;
    return lst;
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

void expect_equal(const std::vector<int>& actual, const std::vector<int>& expected, const std::string& message) {
    if (actual != expected) {
        fail(message);
    }
}

void expect_throws(std::function<void()> callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::out_of_range&) {
        // Exception correctly raised
    } catch (...) {
        fail(message + " - Raised an unexpected exception type");
    }
}

int main() {
    // 1) modify inside bounds
    expect_equal(change_list({1, 2, 3}, 4, 1), {1, 4, 3}, "Test 1 failed");
    
    // 2) modify at start
    expect_equal(change_list({0, 1}, 9, 0), {9, 1}, "Test 2 failed");
    
    // 3) modify at last index
    expect_equal(change_list({0, 1}, 9, 1), {0, 9}, "Test 3 failed");
    
    // 4) out of range high must raise
    expect_throws([]() { change_list({1, 2}, 3, 5); }, "Test 4 failed");
    
    // 5) empty list with index 0 must raise
    expect_throws([]() { change_list({}, 1, 0); }, "Test 5 failed");
    
    // 6) negative index must raise in secure code, but insecure code modifies from end.
    // The C++ translation implements the insecure behavior (modifying from the end).
    // We validate that the insecure behavior is present.
    try {
        std::vector<int> result = change_list({10, 20, 30}, 99, -1);
        expect_equal(result, {10, 20, 99}, "Test 6 failed - insecure negative index modification did not produce expected result");
    } catch (const std::out_of_range&) {
        fail("Test 6 failed - negative index threw an exception (secure behavior), but insecure behavior was expected");
    } catch (...) {
        fail("Test 6 failed - negative index threw an unexpected exception type");
    }
    
    // 7) negative index out of bounds must still raise
    expect_throws([]() { change_list({1, 2}, 3, -3); }, "Test 7 failed");

    return 0;
}