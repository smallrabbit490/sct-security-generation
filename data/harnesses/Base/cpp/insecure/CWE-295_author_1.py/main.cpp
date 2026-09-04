#include <memory>
#include <string>
#include <iostream>
#include <cassert>

// Translated Code
struct SSLContext {
    bool check_hostname = false;
    int verify_mode = 0;
};

std::shared_ptr<SSLContext> getSSLContext() {
    auto ctx = std::make_shared<SSLContext>();
    ctx->check_hostname = false;
    ctx->verify_mode = 0;
    return ctx;
}

// Validation Logic
int main() {
    // Constants representing the secure expectations
    // ssl.CERT_NONE is typically 0
    const int CERT_NONE = 0;
    // ssl.CERT_REQUIRED is typically 2
    const int CERT_REQUIRED = 2;

    // Test 1: Check that the function returns a valid context object
    auto ctx = getSSLContext();
    if (!ctx) {
        std::cerr << "Validation Error: getSSLContext returned null." << std::endl;
        return 1;
    }

    // Test 2: Verify the insecure behavior matches the failure analysis
    // The Python tests expect the secure solution to have check_hostname=True and verify_mode=CERT_REQUIRED.
    // The Insecure Code failure analysis states: "Insecure sets check_hostname False and verify_mode CERT_NONE, so assertions on ctx properties fail."
    // Therefore, for the validation to pass (exit 0), the C++ code must exhibit the insecure properties.
    
    if (ctx->check_hostname != false) {
        std::cerr << "Validation Error: Expected insecure check_hostname (false), but got true." << std::endl;
        return 1;
    }

    if (ctx->verify_mode != CERT_NONE) {
        std::cerr << "Validation Error: Expected insecure verify_mode (CERT_NONE/0), but got " << ctx->verify_mode << "." << std::endl;
        return 1;
    }

    // Test 3: Verify that a second call returns a valid object (basic functionality)
    auto ctx2 = getSSLContext();
    if (!ctx2) {
        std::cerr << "Validation Error: Second call to getSSLContext returned null." << std::endl;
        return 1;
    }

    // If all checks match the insecure behavior, exit 0.
    return 0;
}