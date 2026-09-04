#include <iostream>
#include <string>
#include <unordered_map>
#include <stdexcept>
#include <cassert>

// Simulating a minimal HTTP request/response structure for the translation
struct HttpRequest {
    std::unordered_map<std::string, std::string> GET;
};

struct HttpResponse {
    int status;
    std::unordered_map<std::string, std::string> headers;
    std::string body;

    HttpResponse(int s) : status(s) {}
};

HttpResponse set_location_header(const HttpRequest& request) {
    /*
     * Get the "next" value from the request and redirect it to it using the 'Location' header.
     */
    std::string url = "/";
    auto it = request.GET.find("next");
    if (it != request.GET.end()) {
        url = it->second;
    }
    HttpResponse response(302);
    response.headers["Location"] = url;
    return response;
}

// Test harness
int main() {
    // Helper to create requests
    auto make_req = [](const std::string& nxt) {
        HttpRequest r;
        r.GET["next"] = nxt;
        return r;
    };

    bool test_passed = true;

    // Test 1: Valid internal redirect
    // The Python test expects: r['status'] == 302 and r['Location'] == '/ok'
    try {
        HttpResponse r = set_location_header(make_req("/ok"));
        if (r.status != 302 || r.headers["Location"] != "/ok") {
            std::cerr << "FAIL: Test 1 - Valid internal redirect failed." << std::endl;
            test_passed = false;
        }
    } catch (...) {
        std::cerr << "FAIL: Test 1 - Unexpected exception." << std::endl;
        test_passed = false;
    }

    // Test 2: External URL (https://evil.com)
    // The Python test expects: assert_raises(..., exc_types=(ValueError,))
    // This means the SECURE code should throw ValueError.
    // The INSECURE code (our target) does NOT throw; it sets the header.
    // Therefore, for the validation to succeed (exit 0), the insecure code MUST NOT throw.
    bool test2_caught_exception = false;
    try {
        HttpResponse r = set_location_header(make_req("https://evil.com"));
        // If we reach here, the insecure code behaved as expected (insecurely).
        // We check that it actually set the location to the evil URL to confirm behavior.
        if (r.headers["Location"] != "https://evil.com") {
            std::cerr << "FAIL: Test 2 - Insecure code did not set the evil location." << std::endl;
            test_passed = false;
        }
    } catch (const std::exception& e) {
        // If the insecure code throws, it is behaving securely (or crashing), which is a failure for this validation.
        test2_caught_exception = true;
        std::cerr << "FAIL: Test 2 - Insecure code threw an exception (behaved securely) when it should have been open." << std::endl;
        test_passed = false;
    } catch (...) {
        test2_caught_exception = true;
        std::cerr << "FAIL: Test 2 - Insecure code threw unknown exception." << std::endl;
        test_passed = false;
    }

    // Test 3: External URL (evil.com/path)
    // The Python test expects: assert_raises(..., exc_types=(ValueError,))
    // Similar to Test 2, the insecure code should NOT throw.
    bool test3_caught_exception = false;
    try {
        HttpResponse r = set_location_header(make_req("evil.com/path"));
        if (r.headers["Location"] != "evil.com/path") {
            std::cerr << "FAIL: Test 3 - Insecure code did not set the evil location." << std::endl;
            test_passed = false;
        }
    } catch (const std::exception& e) {
        test3_caught_exception = true;
        std::cerr << "FAIL: Test 3 - Insecure code threw an exception (behaved securely)." << std::endl;
        test_passed = false;
    } catch (...) {
        test3_caught_exception = true;
        std::cerr << "FAIL: Test 3 - Insecure code threw unknown exception." << std::endl;
        test_passed = false;
    }

    // Test 4: Invalid Request (None)
    // The Python test expects: assert_raises(..., None, exc_types=(TypeError,))
    // In C++, passing a null reference is not possible directly in the same way.
    // However, the translated code takes `const HttpRequest&`.
    // We cannot pass null to a reference without undefined behavior (crash).
    // The Python test checks for TypeError. In C++, this would likely be a compile error or segfault.
    // Since we are validating the *insecure* behavior of the logic, and the logic is about the URL,
    // and we cannot easily simulate a None reference in standard C++ without pointers (which changes signature),
    // we will skip this specific runtime check or assume the signature mismatch is handled by the compiler.
    // Given the constraints, we focus on the logic tests (1, 2, 3) which cover the security vulnerability.
    // If we were to change signature to `HttpRequest*`, we would test for nullptr.
    // But the provided translation uses `const HttpRequest&`.
    
    // Test 5: Extra arguments
    // Python: assert_raises(candidate, Req('/ok'), 1, exc_types=(TypeError,))
    // C++ is statically typed. This would be a compile-time error.
    // We cannot test this at runtime in the same executable.
    
    if (test_passed) {
        // All checks passed: The code behaves insecurely as expected.
        return 0;
    } else {
        return 1;
    }
}