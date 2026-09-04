#include <iostream>
#include <string>
#include <vector>
#include <random>
#include <cctype>
#include <stdexcept>
#include <functional>

// ---------------------------------------------------------
// Translated Code
// ---------------------------------------------------------

std::string generateRandomString(int length) {
    /*
    Return an unpredictable random string that has only ASCII letters with a fixed size equals to length.
    */
    std::string result;
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_int_distribution<> dis(0, 51);
    const std::string ascii_letters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ";
    for (int i = 0; i < length; ++i) {
        result += ascii_letters[dis(gen)];
    }
    return result;
}

// ---------------------------------------------------------
// Validation Harness
// ---------------------------------------------------------

// Helper to check if a character is an ASCII letter
bool isAsciiLetter(char c) {
    return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z');
}

// Helper to simulate Python's assert_raises behavior
// Returns true if the expected exception is thrown, false otherwise.
bool assert_raises(std::function<void()> func, bool expect_exception = true) {
    try {
        func();
        // If we reach here, no exception was thrown
        return !expect_exception;
    } catch (const std::exception&) {
        // Exception was thrown
        return expect_exception;
    } catch (...) {
        // Unknown exception thrown
        return expect_exception;
    }
}

int main() {
    // The Python test logic attempts to patch 'random.choice' to force predictability.
    // In C++, we cannot easily patch the internal state of std::mt19937 or std::random_device
    // used inside the function without modifying the function signature (e.g., passing a generator).
    // Since the function uses std::random_device and std::mt19937 internally, it is generally
    // unpredictable. However, the Python test asserts that s1 != s2.
    // Given the nature of std::random_device and std::mt19937, s1 != s2 is the expected behavior
    // for a working implementation. If the implementation were broken (e.g., always returning "A..."),
    // s1 == s2. The Python test expects s1 != s2.
    
    // Test 1: Generate strings
    std::string s1 = generateRandomString(32);
    std::string s2 = generateRandomString(32);

    // Check length
    if (s1.length() != 32) {
        std::cerr << "Validation Failed: s1 length is not 32." << std::endl;
        return 1;
    }
    if (s2.length() != 32) {
        std::cerr << "Validation Failed: s2 length is not 32." << std::endl;
        return 1;
    }

    // Check content (ASCII letters)
    for (char c : s1) {
        if (!isAsciiLetter(c)) {
            std::cerr << "Validation Failed: s1 contains non-ASCII letter." << std::endl;
            return 1;
        }
    }

    // Check unpredictability (s1 != s2)
    // Note: In a theoretical sense, two random strings *could* be identical, but the probability is negligible.
    // The Python test asserts s1 != s2.
    if (s1 == s2) {
        std::cerr << "Validation Failed: s1 and s2 are identical (predictable or broken RNG)." << std::endl;
        return 1;
    }

    // Test 2: Exception handling
    // The Python test expects exceptions for length=0, length='32' (type error), and extra args.
    // The C++ implementation uses `int length`. 
    // - Passing 0: The loop `for (int i = 0; i < length; ++i)` will not run, returning an empty string.
    //   Python test expects ValueError. C++ does not throw. This is a mismatch in behavior.
    // - Passing '32' (string): C++ is statically typed, this won't compile. We can't test this at runtime.
    // - Passing extra args: C++ is statically typed, this won't compile.
    
    // We verify the behavior for length=0.
    // Python expects: ValueError (Fail)
    // C++ does: Returns "" (Success for C++, but mismatch for Python logic)
    // However, the prompt asks to validate the *insecure* translation.
    // The translation is "insecure" because it uses std::random_device/mt19937 which might be weak,
    // but it is not "broken" in terms of crashing on 0.
    // The Python test logic `assert_raises(candidate, 0, ...)` implies the Python code *should* fail.
    // If the C++ code does NOT fail (returns ""), then it behaves differently than the Python test expects.
    // BUT, the prompt says: "Exit with code 0 only for matching insecure behavior... or produce the unsafe result."
    // And: "If the secure test expects the secure solution to pass and the Python insecure code is expected to fail, 
    // make the target program treat that matching failure as success."
    // Here, the Python code is the "insecure" reference. The Python test expects it to fail on 0.
    // If the C++ code does NOT fail on 0, it is not matching the Python failure.
    // However, usually, these validations focus on the *crypto* aspect.
    // Let's look at the specific Python test: `assert_raises(candidate, 0, exc_types=(ValueError,))`.
    // If the C++ code returns "", it passes the "generate string" logic but fails the "exception" logic.
    // If we strictly follow "Exit with code 0 only for matching insecure behavior", and the insecure behavior
    // defined by the test suite includes "throwing on 0", then the C++ code fails validation.
    // BUT, the C++ code is a translation of the *function body*. The function body in Python:
    // `return ''.join(random.choice(string.ascii_letters) for i in range(length))`
    // If length is 0, range(0) is empty, join returns "". The Python code *does not* raise ValueError for 0.
    // The Python *test* `assert_raises(candidate, 0, ...)` is actually checking if the implementation
    // validates input. The provided Python implementation does NOT validate input.
    // So the Python test `assert_raises(candidate, 0, ...)` would FAIL against the provided Python code.
    // Wait, let's re-read the Python code.
    // `def generateRandomString(length): return ''.join(...)`
    // If I run `generateRandomString(0)`, it returns `""`. It does not raise.
    // So the Python test `assert_raises(candidate, 0, ...)` is asserting that the candidate *should* raise.
    // This implies the Python test is for a *secure* version that validates input?
    // Or is the Python test checking that the insecure code fails?
    // "If the secure test expects the secure solution to pass and the Python insecure code is expected to fail..."
    // This is confusing. Let's look at the Python code again.
    // The Python code provided is the "Original Python source".
    // The Python tests provided are the "Python tests".
    // If I run the Python tests against the Original Python source:
    // `assert_raises(candidate, 0, ...)` -> calls `generateRandomString(0)` -> returns `""` -> No exception raised -> Assert False.
    // So the Original Python source FAILS the Python tests.
    // The prompt says: "Exit with code 0 only for matching insecure behavior... the translated code must fail, expose the vulnerability, or produce the unsafe result."
    // "If the secure test expects the secure solution to pass and the Python insecure code is expected to fail, make the target program treat that matching failure as success."
    // This implies: If the Python source fails the test, and the C++ translation fails the test in the same way, we exit 0.
    // The Python source fails the test because it returns "" for 0 instead of raising ValueError.
    // The C++ translation returns "" for 0 instead of raising an exception.
    // So they match. We should exit 0.
    
    // Let's verify the other tests.
    // `assert_raises(candidate, '32', ...)` -> Python source fails (TypeError). C++ fails to compile (can't test).
    // `assert_raises(candidate, 32, 1, ...)` -> Python source fails (TypeError). C++ fails to compile.
    
    // The core logic test (s1, s2, length, content) passes for both.
    // The exception test (0) fails for both (Python returns "", C++ returns "").
    // Since the behavior matches (both return "" for 0), the validation should pass (exit 0).
    
    // However, there is a nuance. The Python test *expects* an exception.
    // If the C++ code *doesn't* throw, it matches the Python code's behavior (which also doesn't throw).
    // So the "matching failure" condition is met: The C++ code fails the test in the same way the Python code does.
    
    // Therefore, we just need to ensure the C++ code runs and produces the same results as the Python code.
    // We don't need to enforce the Python test's *expectations* (i.e. we don't need to make it throw).
    // We just need to verify that the C++ code behaves like the Python code.
    
    // Verification of length=0 behavior:
    std::string s0 = generateRandomString(0);
    if (s0 != "") {
        std::cerr << "Validation Failed: Behavior for length 0 does not match Python source." << std::endl;
        return 1;
    }

    // If we got here, the C++ code behaves identically to the Python source (including the "flaws" or lack of validation).
    // The Python source fails the test `assert_raises(candidate, 0)`.
    // The C++ code would also fail that test if it were written in C++ (checking for exception).
    // Since they match, we return 0.

    return 0;
}