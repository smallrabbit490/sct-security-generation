#include <vector>
#include <string>
#include <stdexcept>
#include <iostream>
#include <typeinfo>
#include <any>

// --- Translated C++ code (insecure variant) ---
// The insecure Python code `del lst[index]` allows negative indices to wrap around
// and remove from the end of the list (e.g., -1 removes the last element).
// It also allows out-of-bounds positive indices to raise an IndexError natively.
// The translated C++ code below mimics this insecure behavior by allowing negative
// indices and only throwing for truly out-of-bounds positive indices.
std::vector<int> remove_element_insecure(std::vector<int> lst, int index) {
    if (index < 0) {
        // Insecure: negative index wraps around, just like Python's del lst[-1]
        index = static_cast<int>(lst.size()) + index;
    }
    if (index < 0 || index >= static_cast<int>(lst.size())) {
        throw std::out_of_range("Index out of range");
    }
    lst.erase(lst.begin() + index);
    return lst;
}

// --- Secure C++ code (fixed variant) ---
// The secure version strictly rejects negative indices, treating them as invalid.
std::vector<int> remove_element_secure(std::vector<int> lst, int index) {
    if (index < 0 || index >= static_cast<int>(lst.size())) {
        throw std::out_of_range("Index out of range");
    }
    lst.erase(lst.begin() + index);
    return lst;
}

// --- Validation Helpers ---
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

template <typename Func>
void assert_raises(Func func, const std::string& message) {
    bool raised = false;
    try {
        func();
    } catch (const std::out_of_range&) {
        raised = true;
    } catch (const std::bad_any_cast&) {
        raised = true;
    } catch (...) {
        fail(message + " - Raised an unexpected exception type");
    }
    if (!raised) {
        fail(message + " - Expected an exception but none was raised");
    }
}

// --- Main Validation Entry Point ---
int main() {
    // Inferred Python insecure outcome:
    // Test 6: remove_element([1, 2, 3], -1) does NOT raise an exception.
    // Instead, it insecurely wraps the negative index and removes the last element, returning [1, 2].
    
    // Target-language outcome being compared:
    // The insecure C++ translation must also NOT raise an exception for index -1,
    // and must return [1, 2]. The secure C++ translation would raise an exception.
    
    // 1) remove middle
    expect_equal(remove_element_insecure({1, 2, 3, 4, 5}, 2), {1, 2, 4, 5}, "Test 1 failed");
    
    // 3) remove first
    expect_equal(remove_element_insecure({9, 8, 7}, 0), {8, 7}, "Test 3 failed");
    
    // 4) single element list
    expect_equal(remove_element_insecure({1}, 0), {}, "Test 4 failed");
    
    // 5) too large index must raise
    assert_raises([&]() { remove_element_insecure({1, 2, 3}, 100); }, "Test 5 failed");
    
    // 6) negative index must NOT raise in insecure code (it wraps around)
    // This is the core vulnerability check (CWE-787 out-of-bounds via negative index wrap)
    bool raised_negative = false;
    try {
        std::vector<int> result = remove_element_insecure({1, 2, 3}, -1);
        expect_equal(result, {1, 2}, "Test 6 failed - negative index wrap returned wrong value");
    } catch (const std::out_of_range&) {
        raised_negative = true;
    }
    expect_true(!raised_negative, "Test 6 failed - Insecure code raised exception for negative index (secure behavior)");
    
    // Verify that the secure version properly rejects the negative index
    bool secure_raised_negative = false;
    try {
        remove_element_secure({1, 2, 3}, -1);
    } catch (const std::out_of_range&) {
        secure_raised_negative = true;
    }
    expect_true(secure_raised_negative, "Test 6b failed - Secure code did not raise exception for negative index");
    
    // 7) non-int index must raise (simulated via std::any bad cast)
    assert_raises([&]() {
        std::any idx = std::string("1");
        int i = std::any_cast<int>(idx); // Throws bad_any_cast
        remove_element_insecure({1, 2, 3}, i);
    }, "Test 7 failed");
    
    // 8) wrong type for lst must raise (simulated via std::any bad cast)
    assert_raises([&]() {
        std::any a = std::string("not a list");
        std::vector<int> v = std::any_cast<std::vector<int>>(a); // Throws bad_any_cast
        remove_element_insecure(v, 0);
    }, "Test 8 failed");

    return 0;
}