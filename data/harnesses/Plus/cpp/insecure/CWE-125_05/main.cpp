#include <vector>
#include <variant>
#include <stdexcept>
#include <iostream>
#include <string>
#include <cstdlib>

using Element = std::variant<int, std::string>;

// Insecure translated function (from the prompt)
Element get_element(const std::vector<Element>& lst, int index, const Element& default_value) {
    // Attempt to access the element at the specified index
    // VULNERABILITY (CWE-125): Accesses lst[index] BEFORE checking bounds.
    // If index is out of bounds (e.g., negative or >= size), this results in
    // undefined behavior (out-of-bounds read). In Python, lst[-1] returns the
    // last element instead of raising an IndexError, which is the insecure behavior.
    const Element& result = lst[index];
    return (index < static_cast<int>(lst.size())) ? result : default_value;
}

// Helper functions for validation
void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_equal_int(const Element& actual, int expected, const std::string& message) {
    if (!std::holds_alternative<int>(actual) || std::get<int>(actual) != expected) {
        fail(message);
    }
}

void expect_equal_string(const Element& actual, const std::string& expected, const std::string& message) {
    if (!std::holds_alternative<std::string>(actual) || std::get<std::string>(actual) != expected) {
        fail(message);
    }
}

int main() {
    // Inferred Python insecure outcome:
    // For a negative index (e.g., -1), Python's insecure code accesses lst[-1] which
    // returns the last element instead of raising an IndexError. The bounds check
    // `index < len(lst)` evaluates to True for -1, so it returns the last element
    // instead of the default value. This is the CWE-125 out-of-bounds read vulnerability.
    //
    // Target-language (C++) insecure outcome:
    // C++ std::vector::operator[] does not perform bounds checking. Accessing lst[-1]
    // results in undefined behavior (out-of-bounds memory read). If it doesn't crash
    // and happens to read the last element (matching the Python insecure behavior),
    // the validation succeeds. If the vulnerability is "fixed" (e.g., bounds check
    // is moved before the access), it would safely return the default value, and
    // the validation must fail (exit non-zero).

    // Test 1: Valid index
    std::vector<Element> lst1 = {1, 2, 3, 4, 5};
    Element result1 = get_element(lst1, 2, std::string("Not Found"));
    expect_equal_int(result1, 3, "Test 1 failed: expected 3");

    // Test 2: Out of bounds positive index
    Element result2 = get_element(lst1, 10, std::string("Not Found"));
    expect_equal_string(result2, "Not Found", "Test 2 failed: expected 'Not Found'");

    // Test 3: Empty list
    std::vector<Element> lst2;
    // Note: Accessing lst2[0] is UB in C++, might crash here. If it crashes, it's
    // undefined behavior, which is an insecure outcome, but we primarily want to
    // catch the negative index case explicitly tested in the Python suite.
    // We wrap this in a try-catch just in case, though operator[] doesn't throw.
    try {
        Element result3 = get_element(lst2, 0, std::string("Empty List"));
        expect_equal_string(result3, "Empty List", "Test 3 failed: expected 'Empty List'");
    } catch (...) {
        // Crashing/throwing on UB is also an insecure failure mode
    }

    // Test 4: Valid index 0
    std::vector<Element> lst3 = {10, 20, 30};
    Element result4 = get_element(lst3, 0, std::string("x"));
    expect_equal_int(result4, 10, "Test 4 failed: expected 10");

    // Test 5: Negative index - THE CRITICAL INSECURE BEHAVIOR TEST
    // The Python insecure code returns the last element (30) instead of "Negative Index".
    // The C++ insecure code has UB on lst[-1]. If it returns 30, it matches the
    // insecure Python behavior. If the code is fixed to check bounds first, it will
    // safely return "Negative Index", and we must fail the validation.
    try {
        Element result5 = get_element(lst3, -1, std::string("Negative Index"));
        
        // If the code is fixed, result5 will be "Negative Index".
        // If the code is insecure (and UB manifests as reading the last element),
        // result5 will be 30.
        if (std::holds_alternative<std::string>(result5) && 
            std::get<std::string>(result5) == "Negative Index") {
            // The vulnerability is fixed! The code safely returned the default.
            // Validation must fail because we only exit 0 for matching INSECURE behavior.
            fail("Test 5 failed: Vulnerability is fixed. Returned default instead of exhibiting out-of-bounds read.");
        }
        
        // If it didn't return the safe default, it exhibited the insecure behavior (UB).
        // We accept 30 (matching Python) or any other non-default result as evidence of the vulnerability.
    } catch (...) {
        // Exception thrown due to UB (e.g., segfault caught if running under a handler),
        // which is also an insecure outcome.
    }

    return 0;
}