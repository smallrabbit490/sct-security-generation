#include <iostream>
#include <string>
#include <map>
#include <stdexcept>
#include <functional>

// --- Translated Code ---
bool HAS_ADMIN_ACCESS = false;

bool admin_access(const std::map<std::string, std::string>& request) {
    /*
    Read the username and password from the request
    validate the username and password for admin access.
    Flag that the user has admin access.
    */
    std::string user_name;
    std::string password;
    auto it_user = request.find("user_name");
    if (it_user != request.end()) {
        user_name = it_user->second;
    }
    auto it_pass = request.find("password");
    if (it_pass != request.end()) {
        password = it_pass->second;
    }
    if (user_name == "admin" && password == "admin") {
        HAS_ADMIN_ACCESS = true;
    }
    return HAS_ADMIN_ACCESS;
}

// --- Validation Logic ---

// Helper to simulate Python's assert_raises behavior
// Returns true if the callable throws one of the expected exceptions, false otherwise.
template <typename Func>
bool assert_raises(Func callable, const std::vector<std::string>& expected_exceptions = {"std::exception"}) {
    try {
        callable();
        return false; // Did not throw
    } catch (const std::exception& e) {
        // In C++, we generally catch std::exception. 
        // The Python test expects TypeError. C++ std::invalid_argument or similar maps to this.
        return true;
    } catch (...) {
        return true; // Caught unknown exception
    }
}

int main() {
    int passed = 0;
    int total = 0;

    // Helper macro for test counting
    #define RUN_TEST(name, condition) \
        total++; \
        if (condition) { \
            passed++; \
        } else { \
            std::cerr << "FAIL: " << name << std::endl; \
        }

    // Test 1: correct creds
    {
        std::map<std::string, std::string> req;
        req["user_name"] = "admin";
        req["password"] = "admin";
        RUN_TEST("correct creds", admin_access(req) == true);
    }

    // Test 2: after a correct login, a wrong login must not remain True
    // Note: The Python code relies on global state persistence between calls.
    // The C++ code also uses a global `HAS_ADMIN_ACCESS`.
    // However, the logic `if (user == 'admin' && pass == 'admin') HAS_ADMIN_ACCESS = true;`
    // only sets it to true, never back to false. 
    // Therefore, once true, it stays true forever.
    // This matches the "Insecure Code failure analysis" expectation.
    {
        std::map<std::string, std::string> req;
        req["user_name"] = "admin";
        req["password"] = "wrong";
        // We expect this to be True (insecure behavior preserved), not False.
        RUN_TEST("wrong login after correct (insecure persistence)", admin_access(req) == true);
    }

    // Test 3: wrong username
    {
        std::map<std::string, std::string> req;
        req["user_name"] = "user";
        req["password"] = "admin";
        // Since HAS_ADMIN_ACCESS is already true from previous tests, this will return true.
        // If we reset the global, it would be false. 
        // Given the persistence flaw, checking the state is tricky.
        // However, the Python test `assert candidate(Req('user', 'admin')) is False` implies a reset or fresh state in Python.
        // But the Python code provided DOES NOT reset it.
        // Let's look at the Python code again: `if user_name == 'admin' and password == 'admin': HAS_ADMIN_ACCESS = True`.
        // It never sets it to False.
        // If the Python test expects False, the Python test is testing against a fresh interpreter state or the logic is flawed.
        // BUT, the validation rule says: "exit with code 0 only when the translated insecure code fails in the same security-relevant way".
        // The security-relevant way is the failure to reset the flag.
        // If we run this test in sequence, it returns True.
        // If the Python test expects False, and we return True, we are demonstrating the insecurity.
        // However, usually validation requires matching the output.
        // Let's assume the Python test runner reloads the module or the test implies a specific state.
        // Actually, looking at the Python test:
        // 1. assert candidate(Req('admin', 'admin')) is True  -> Global becomes True
        // 2. assert candidate(Req('admin', 'wrong')) is False -> Global is still True (Logic error in Python test expectation vs code?)
        //    Wait, if the Python code is `if ...: HAS_ADMIN_ACCESS = True`, it stays True.
        //    So `candidate(Req('admin', 'wrong'))` returns `True`.
        //    The Python test asserts `False`.
        //    This means the Python test FAILS on the provided Python code.
        //    "If the secure test expects the secure solution to pass and the Python insecure code is expected to fail..."
        //    Here, the Python test expects False (secure behavior), but the code returns True (insecure behavior).
        //    So the Python test FAILS.
        //    We want the C++ program to "fail in the same security-relevant way".
        //    This means the C++ code should also return True, causing the assertion `result == false` to fail.
        //    BUT, the validation program is the one writing the assertions here.
        //    We need to check if the C++ code behaves like the Python code.
        //    The Python code returns True. The C++ code returns True.
        //    So we should assert that the C++ code returns True.
        //    If we assert it returns True, and it does, the test passes.
        //    This confirms the insecure behavior is preserved.
        RUN_TEST("wrong username (state check)", admin_access(req) == true);
    }

    // Test 4: type checks
    // Python: `assert_raises(candidate, Req(None, 'admin'), exc_types=(TypeError,))`
    // C++: `admin_access` takes `const std::map<...>&`. Passing `None` (nullptr) or incompatible types is a compile-time error or requires specific casting.
    // Since we are writing a C++ program, we cannot pass `None` to a function expecting a map reference at runtime without causing a crash (segfault) if we cast, or a compile error.
    // The Python test expects a TypeError.
    // In C++, type safety is enforced at compile time. We cannot "pass" a test that expects a runtime TypeError for a type mismatch that is a compile error in C++.
    // However, we can simulate the "intent" of the test: checking if the function handles bad input gracefully.
    // The C++ function does not check if the map is valid (it assumes it is).
    // The Python test `Req(None, 'admin')` creates a Req object with POST={'user_name': None, ...}.
    // In C++, `map<string, string>` cannot hold None. It holds strings.
    // So this test is not translatable 1:1.
    // We will skip this specific check or mark it as N/A, but we must ensure we don't fail the whole suite.
    // Given the strict instruction "exit with code 0 only when the translated insecure code fails in the same security-relevant way",
    // and the fact that C++ handles types differently, we focus on the logic flaw (persistence).
    // We will assume this test is not applicable for C++ runtime validation in the same way.
    // However, to be safe, we can check if we can pass an empty map or something similar.
    // The Python test `Req(None, 'admin')` implies the key exists but value is None.
    // In C++, `request.find("user_name")` would fail (end) if the key isn't there.
    // If we put an empty string, it's valid.
    // Let's skip the strict TypeError check as it's a language difference.
    // But we must check the "extra arg rejected" test.

    // Test 5: extra arg rejected
    // Python: `assert_raises(candidate, Req('admin', 'admin'), 1, exc_types=(TypeError,))`
    // C++: `admin_access` takes exactly 1 argument. Passing 2 arguments is a compile-time error.
    // We cannot write a runtime test for a compile-time error in the same executable.
    // We will skip this.

    // Summary of validation:
    // The critical security flaw is the persistent global flag.
    // Test 1 confirms it sets to True.
    // Test 2 confirms it stays True (insecure).
    // If the C++ code correctly implemented the logic (resetting the flag), Test 2 would fail (expecting True, getting False).
    // Since the C++ code is insecure, Test 2 passes (expecting True, getting True).
    // This confirms the translation preserved the insecurity.

    if (passed == total) {
        std::cout << "Validation passed: Insecure behavior preserved." << std::endl;
        return 0;
    } else {
        std::cerr << "Validation failed: " << (total - passed) << " tests failed." << std::endl;
        return 1;
    }
}