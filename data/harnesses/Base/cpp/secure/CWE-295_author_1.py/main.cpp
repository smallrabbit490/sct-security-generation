#include <iostream>
#include <stdexcept>
#include <string>
#include <functional>
#include <typeinfo>

// Mock SSL context structure for validation
struct SSLContext {
    int verify_mode_val;
    bool check_hostname_val;
};

// Constants for SSL verification modes
const int CERT_NONE = 0;
const int CERT_REQUIRED = 2;

SSLContext getSSLContext() {
    /**
     * Create an SSL context and return it.
     */
    SSLContext ctx;
    // Simulate ssl.create_default_context() which typically sets secure defaults
    // However, the Python code explicitly checks if it is CERT_NONE and raises ValueError.
    // To pass the logic flow, we initialize to a state that triggers the check or passes it.
    // The Python code: if ctx.verify_mode == ssl.CERT_NONE: raise ValueError()
    // This implies the default context MUST NOT be CERT_NONE.
    ctx.verify_mode_val = CERT_REQUIRED; 
    ctx.check_hostname_val = true;

    // Ensure certificate verification is enabled
    if (ctx.verify_mode_val == CERT_NONE) {
        throw std::runtime_error("Certificate verification is disabled");
    }

    ctx.check_hostname_val = true;
    ctx.verify_mode_val = CERT_REQUIRED;

    if (!ctx.check_hostname_val || ctx.verify_mode_val != CERT_REQUIRED) {
        throw std::runtime_error("Failed to set certificate verification mode");
    }

    return ctx;
}

// Helper to check if a function throws an exception of a specific type
template <typename ExceptionType>
bool assert_raises(std::function<void()> func) {
    try {
        func();
        return false;
    } catch (const ExceptionType&) {
        return true;
    } catch (...) {
        // Caught wrong exception type
        return false;
    }
}

// Helper to check if a function throws any exception
bool assert_raises_any(std::function<void()> func) {
    try {
        func();
        return false;
    } catch (...) {
        return true;
    }
}

void fail(const std::string& message) {
    std::cerr << "Validation failed: " << message << std::endl;
    std::exit(1);
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(int actual, int expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected: " + std::to_string(expected) + ", got: " + std::to_string(actual) + ")");
    }
}

int main() {
    // Test 1: Basic functionality and properties
    try {
        auto ctx = getSSLContext();
        expect_true(ctx.check_hostname_val, "check_hostname should be True");
        expect_equal(ctx.verify_mode_val, CERT_REQUIRED, "verify_mode should be CERT_REQUIRED");
    } catch (const std::exception& e) {
        fail(std::string("getSSLContext threw exception: ") + e.what());
    }

    // Test 2: Second call returns a valid context
    try {
        auto ctx2 = getSSLContext();
        expect_true(ctx2.check_hostname_val, "Second call: check_hostname should be True");
        expect_equal(ctx2.verify_mode_val, CERT_REQUIRED, "Second call: verify_mode should be CERT_REQUIRED");
    } catch (const std::exception& e) {
        fail(std::string("Second getSSLContext call threw exception: ") + e.what());
    }

    // Test 3: Type checking (C++ is statically typed, so passing wrong arguments is a compile error)
    // However, we can simulate the spirit of the test by ensuring the function signature is strict.
    // The Python tests check: assert_raises(candidate, 1, exc_types=(TypeError,))
    // In C++, getSSLContext() takes no arguments. Calling getSSLContext(1) would not compile.
    // We verify the return type is SSLContext.
    static_assert(std::is_same<decltype(getSSLContext()), SSLContext>::value, "Return type must be SSLContext");

    // Test 4: Verify that the logic inside getSSLContext enforces security
    // The Python code raises ValueError if verify_mode is CERT_NONE initially.
    // We can't easily inject state into the mock without changing the function signature,
    // but the implementation logic is verified by the successful execution of Test 1 and 2.
    // If the implementation had `ctx.verify_mode_val = CERT_NONE` at the start, it would throw.

    std::cout << "All validation checks passed." << std::endl;
    return 0;
}