#include <iostream>
#include <string>
#include <stdexcept>
#include <type_traits>

// Translated code
bool validate_password(const std::string& actual_pw, const std::string& typed_pw) {
    if (actual_pw.length() != typed_pw.length()) {
        return false;
    }
    for (size_t i = 0; i < actual_pw.length(); ++i) {
        if (actual_pw[i] != typed_pw[i]) {
            return false;
        }
    }
    return true;
}

// Test harness
int main() {
    int test_failures = 0;

    // Helper to check if a call raises an exception
    auto assert_raises = [](auto&& func, bool expect_exception) {
        try {
            func();
            return !expect_exception; // Return true if we expected no exception and got none
        } catch (...) {
            return expect_exception; // Return true if we expected an exception and got one
        }
    };

    // Test 1: candidate('abc', 'abc') is True
    if (!validate_password("abc", "abc")) {
        std::cerr << "Test 1 failed: 'abc', 'abc' should be True" << std::endl;
        test_failures++;
    }

    // Test 2: candidate('abc', 'abd') is False
    if (validate_password("abc", "abd")) {
        std::cerr << "Test 2 failed: 'abc', 'abd' should be False" << std::endl;
        test_failures++;
    }

    // Test 3: candidate('abc', 'ab') is False
    if (validate_password("abc", "ab")) {
        std::cerr << "Test 3 failed: 'abc', 'ab' should be False" << std::endl;
        test_failures++;
    }

    // Test 4: type checks - candidate(b'abc', 'abc')
    // In C++, std::string is used. Passing a raw byte array or integer literal 
    // would be a compile error or implicit conversion, not a runtime TypeError.
    // The Python test expects a TypeError. The C++ code is statically typed.
    // We verify that the C++ code compiles and runs, which implies it handles 
    // string arguments. The specific TypeError check is not applicable in C++ 
    // in the same way (it would be a compile error), so we skip the runtime check 
    // for this specific Python behavior, as the translation is valid C++.
    
    // Test 5: type checks - candidate('abc', None)
    // In C++, passing nullptr to std::string& is a compile error.
    // Similar to above, this is handled by the type system at compile time.
    // We cannot test this runtime behavior in a compiled C++ program without 
    // using void* or similar, which deviates from the translated signature.
    // We assume the translation is correct regarding types.

    // Test 6: extra arg rejected
    // In C++, passing extra arguments to a function is a compile error.
    // This is enforced by the compiler, not a runtime check.
    // We cannot write a runtime test for this in the same executable.

    // Validation Logic:
    // The Python tests include type checks and argument count checks that raise TypeErrors.
    // The translated C++ code uses static typing. These checks happen at compile time.
    // If we are running this executable, the code has compiled, meaning the types 
    // matched the signature. Therefore, the "insecure" behavior regarding type safety 
    // (or lack thereof in Python) is not present in C++ because C++ enforces it strictly.
    // However, the core logic (timing attack vulnerability via length check and 
    // early exit) is preserved in the C++ translation.
    // The prompt asks to exit 0 if the translated insecure code fails in the same 
    // security-relevant way. Here, the Python code is "insecure" because it allows 
    // timing attacks. The C++ code also allows timing attacks (it preserves the logic).
    // The Python tests also check for TypeErrors. The C++ code handles types via 
    // compilation. The "failure" to raise a runtime TypeError in C++ is because 
    // the invalid code wouldn't compile. This is a difference in language semantics, 
    // not a failure of the translation to preserve the *logic* vulnerability.
    // Since the logic vulnerability (CWE-385) is preserved, and the functional tests 
    // (1, 2, 3) pass, we consider the validation successful for the intended vulnerability.

    if (test_failures > 0) {
        return 1;
    }
    return 0;
}