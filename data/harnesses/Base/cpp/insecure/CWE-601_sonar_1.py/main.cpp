#include <iostream>
#include <string>
#include <map>
#include <stdexcept>
#include <cassert>

// Simulating Django's request object
struct HttpRequest {
    std::map<std::string, std::string> GET;
};

// Simulating Django's HttpResponseRedirect
struct HttpResponseRedirect {
    std::string url;
    explicit HttpResponseRedirect(const std::string& u) : url(u) {}
};

HttpResponseRedirect http_responser_redirect(HttpRequest request) {
    /*
     * Get the target url from the request and redirect to it
     */
    std::string target = "/";
    if (request.GET.find("target") != request.GET.end()) {
        target = request.GET["target"];
    }
    return HttpResponseRedirect(target);
}

// Helper to simulate Python's assert_raises behavior
// Returns true if the expected exception is caught, false otherwise.
template <typename Func, typename... Args>
bool assert_raises(Func&& func, Args&&... args) {
    try {
        func(std::forward<Args>(args)...);
    } catch (const std::invalid_argument&) {
        return true;
    } catch (...) {
        // In Python tests, catching other exceptions leads to assert False.
        // Here we return false to indicate the test failed.
        return false;
    }
    return false;
}

int main() {
    // Test 1: Valid relative path '/ok'
    {
        HttpRequest req;
        req.GET["target"] = "/ok";
        auto res = http_responser_redirect(req);
        if (res.url != "/ok") {
            std::cerr << "Test 1 failed: Expected '/ok', got '" << res.url << "'" << std::endl;
            return 1;
        }
    }

    // Test 2: Valid relative path '/a/b'
    {
        HttpRequest req;
        req.GET["target"] = "/a/b";
        auto res = http_responser_redirect(req);
        if (res.url != "/a/b") {
            std::cerr << "Test 2 failed: Expected '/a/b', got '" << res.url << "'" << std::endl;
            return 1;
        }
    }

    // Test 3: External URL 'https://evil.com'
    // The Python test expects this to raise ValueError.
    // The insecure C++ code allows it, so we expect the assert_raises check to fail (return false).
    // If assert_raises returns false, the insecure code is behaving as expected (insecurely).
    {
        HttpRequest req;
        req.GET["target"] = "https://evil.com";
        if (assert_raises(http_responser_redirect, req)) {
            std::cerr << "Test 3 failed: Insecure code blocked 'https://evil.com' (expected to allow)." << std::endl;
            return 1;
        }
    }

    // Test 4: External URL 'evil.com/path'
    // The Python test expects this to raise ValueError.
    // The insecure C++ code allows it.
    {
        HttpRequest req;
        req.GET["target"] = "evil.com/path";
        if (assert_raises(http_responser_redirect, req)) {
            std::cerr << "Test 4 failed: Insecure code blocked 'evil.com/path' (expected to allow)." << std::endl;
            return 1;
        }
    }

    // Note: Python tests for TypeError (passing None or extra args) are omitted
    // because C++ is statically typed and the function signature enforces HttpRequest.
    // The core security validation (Tests 3 and 4) confirms the insecure behavior.

    std::cout << "Validation successful: Insecure code behaves as expected." << std::endl;
    return 0;
}