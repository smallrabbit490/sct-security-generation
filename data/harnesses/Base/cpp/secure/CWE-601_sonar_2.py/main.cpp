#include <iostream>
#include <string>
#include <stdexcept>
#include <algorithm>
#include <cctype>
#include <map>
#include <cassert>

// Mocking the request object for the sake of the translation.
// In a real C++ web framework, this would be provided by the framework.
struct Request {
    struct Args {
        std::map<std::string, std::string> data;

        std::string get(const std::string& key) const {
            auto it = data.find(key);
            if (it != data.end()) {
                return it->second;
            }
            return "";
        }
    } args;
};

// Global request object (simulating Flask's global request)
// Initialized to nullptr to simulate the check in the Python code
Request* request = nullptr;

std::string flask_redirect() {
    // Check if request is available and has args
    // The Python code checks: if 'request' not in globals() or request is None or not hasattr(request, 'args')
    // In C++, we check if the global pointer is null.
    if (request == nullptr) {
        throw std::runtime_error("Request is not available");
    }

    // Get the 'next' parameter from the request
    std::string url = request->args.get("next");

    // Check if url is a string (implicitly true in C++ for std::string)
    // Strip whitespace from the URL
    url.erase(url.begin(), std::find_if(url.begin(), url.end(), [](int ch) { return !std::isspace(ch); }));
    url.erase(std::find_if(url.rbegin(), url.rend(), [](int ch) { return !std::isspace(ch); }).base(), url.end());

    if (url.empty()) {
        throw std::invalid_argument("URL cannot be empty");
    }

    // Check for scheme or netloc (simplified check)
    // Python: if parts.scheme or parts.netloc: raise ValueError()
    // We check for "://" to identify a scheme.
    size_t scheme_pos = url.find("://");
    if (scheme_pos != std::string::npos) {
        throw std::invalid_argument("URL cannot contain a scheme");
    }

    // Check if URL starts with '/'
    if (url[0] != '/') {
        throw std::invalid_argument("URL must start with '/'");
    }

    return url;
}

// Helper to check if a function throws a specific exception type
template <typename Func, typename... Args>
bool assert_raises(Func func, Args&&... args) {
    try {
        func(std::forward<Args>(args)...);
    } catch (const std::invalid_argument&) {
        return true;
    } catch (const std::runtime_error&) {
        return true;
    } catch (...) {
        return false;
    }
    return false;
}

int main() {
    bool all_passed = true;

    // Test 1: Valid redirect to /dashboard
    {
        Request req;
        req.args.data["next"] = "/dashboard";
        request = &req;
        try {
            std::string result = flask_redirect();
            if (result != "/dashboard") {
                std::cerr << "Test 1 Failed: Expected '/dashboard', got '" << result << "'" << std::endl;
                all_passed = false;
            }
        } catch (...) {
            std::cerr << "Test 1 Failed: Unexpected exception" << std::endl;
            all_passed = false;
        }
    }

    // Test 2: Valid redirect with query params
    {
        Request req;
        req.args.data["next"] = "/x?y=1";
        request = &req;
        try {
            std::string result = flask_redirect();
            if (result != "/x?y=1") {
                std::cerr << "Test 2 Failed: Expected '/x?y=1', got '" << result << "'" << std::endl;
                all_passed = false;
            }
        } catch (...) {
            std::cerr << "Test 2 Failed: Unexpected exception" << std::endl;
            all_passed = false;
        }
    }

    // Test 3: Invalid redirect with scheme (https://evil.com)
    {
        Request req;
        req.args.data["next"] = "https://evil.com";
        request = &req;
        if (!assert_raises(flask_redirect)) {
            std::cerr << "Test 3 Failed: Expected ValueError for 'https://evil.com'" << std::endl;
            all_passed = false;
        }
    }

    // Test 4: Empty string
    {
        Request req;
        req.args.data["next"] = "";
        request = &req;
        if (!assert_raises(flask_redirect)) {
            std::cerr << "Test 4 Failed: Expected ValueError for empty string" << std::endl;
            all_passed = false;
        }
    }

    // Test 5: Request is None (simulated by nullptr)
    {
        request = nullptr;
        if (!assert_raises(flask_redirect)) {
            std::cerr << "Test 5 Failed: Expected TypeError/Exception for None request" << std::endl;
            all_passed = false;
        }
    }

    if (all_passed) {
        std::cout << "All tests passed." << std::endl;
        return 0;
    } else {
        return 1;
    }
}