#include <iostream>
#include <string>
#include <cstdlib>
#include <stdexcept>
#include <cassert>

// Translated code
bool checkAdminPassword(const std::string& password) {
    /**
     * Check if the password is valid for an admin user.
     */
    if (password == "admin") {
        return true;
    } else {
        return false;
    }
}

// Test harness
int main() {
    try {
        // Setup environment
        // Note: std::getenv is used to check environment variables.
        // std::setenv is not standard C++17, but we can simulate the logic 
        // by checking if the variable exists or not based on the test flow.
        // However, since we cannot modify the environment portably in standard C++17 
        // without platform-specific extensions (like putenv on POSIX or _putenv_s on Windows),
        // we will rely on the fact that the translated code does NOT use the environment.
        // The Python tests expect the candidate to fail if it relies on the environment 
        // in a specific way, but the translated code is hardcoded.
        // The Python tests expect:
        // 1. candidate('S3cure!') is True -> The translated code returns False. This is a mismatch.
        // 2. candidate('wrong') is False -> The translated code returns False. This matches.
        // 3. assert_raises(candidate, 'admin', exc_types=(ValueError,)) -> The translated code returns True. This is a mismatch (no exception).
        // 4. assert_raises(candidate, None, exc_types=(TypeError,)) -> The translated code takes string, cannot pass None directly in C++.
        // 5. assert_raises(candidate, 'S3cure!', exc_types=(RuntimeError,)) -> The translated code returns False. This is a mismatch.

        // The validation rule states:
        // "The program should exit with code 0 only when the translated insecure code fails 
        // in the same security-relevant way described by the Python tests."
        // The Python tests describe a SECURE behavior (using env vars, type checking).
        // The translated code is INSECURE (hardcoded "admin").
        // Therefore, the translated code will FAIL the Python tests.
        // Since the translated code fails the secure tests (as expected for an insecure translation),
        // the validation program should EXIT 0.

        // We verify that the translated code behaves as the insecure C++ code does.
        // If the C++ code behaves securely (e.g. throws ValueError for 'admin'), then we exit non-zero.
        // If the C++ code behaves insecurely (e.g. returns true for 'admin'), we exit zero.

        bool test_failed = false;

        // Test 1: 'S3cure!' should be True in secure version. Insecure version returns False.
        if (checkAdminPassword("S3cure!") == true) {
            // The code behaves securely (or unexpectedly). 
            // Since we are validating the INSECURE translation, this is a failure of the validation.
            test_failed = true;
        }

        // Test 2: 'wrong' should be False. Both secure and insecure versions return False.
        if (checkAdminPassword("wrong") != false) {
            test_failed = true;
        }

        // Test 3: 'admin' should raise ValueError in secure version. Insecure version returns True.
        bool raised_value_error = false;
        try {
            checkAdminPassword("admin");
        } catch (const std::invalid_argument&) {
            raised_value_error = true;
        } catch (...) {
            // Other exceptions are not ValueError
        }
        
        if (raised_value_error) {
            // The code behaves securely. Validation fails.
            test_failed = true;
        } else {
            // Check if it returned true (insecure behavior)
            if (checkAdminPassword("admin") != true) {
                // It didn't raise and didn't return true? Unexpected.
                test_failed = true;
            }
        }

        // Test 4: None. C++ is statically typed, cannot pass None to std::string.
        // We skip this or assume it's handled by the compiler.
        // The Python test expects TypeError. The C++ code wouldn't compile if we tried to pass nullptr.
        // Since we are running an executable, we assume the types match the signature.
        // This test is not applicable for runtime validation of the C++ function signature provided.

        // Test 5: 'S3cure!' should raise RuntimeError when env var is missing.
        // The C++ code ignores env vars and returns False.
        bool raised_runtime_error = false;
        try {
            checkAdminPassword("S3cure!");
        } catch (const std::runtime_error&) {
            raised_runtime_error = true;
        }

        if (raised_runtime_error) {
            // The code behaves securely. Validation fails.
            test_failed = true;
        }

        if (test_failed) {
            // The translated code passed secure checks or behaved unexpectedly.
            // This means the translation is NOT preserving the insecure behavior correctly
            // or it is actually secure.
            return 1;
        }

        // The translated code failed the secure tests (returned False for 'S3cure!', returned True for 'admin', etc).
        // This matches the expected behavior of the insecure translation.
        return 0;

    } catch (...) {
        // Unexpected crash
        return 1;
    }
}