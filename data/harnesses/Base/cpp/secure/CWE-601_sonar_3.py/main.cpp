#include <iostream>
#include <string>
#include <unordered_map>
#include <stdexcept>
#include <algorithm>
#include <cctype>
#include <cassert>

// Mock request object for demonstration; in a real scenario, this would be provided by the framework.
struct RequestArgs {
    std::string get(const std::string& key) const {
        auto it = args.find(key);
        return (it != args.end()) ? it->second : "";
    }
    std::unordered_map<std::string, std::string> args;
};

struct Request {
    RequestArgs args;
};

// Global request object (simulating Flask's request)
Request* request = nullptr;

std::unordered_map<std::string, std::string> set_location_header() {
    if (request == nullptr) {
        throw std::runtime_error("Request is null");
    }

    std::string url = request->args.get("next");
    if (url.empty()) {
        throw std::runtime_error("URL is empty");
    }

    // Trim whitespace
    url.erase(url.begin(), std::find_if(url.begin(), url.end(), [](int ch) {
        return !std::isspace(ch);
    }));
    url.erase(std::find_if(url.rbegin(), url.rend(), [](int ch) {
        return !std::isspace(ch);
    }).base(), url.end());

    if (url.empty()) {
        throw std::runtime_error("URL is empty after trimming");
    }

    // Check for scheme or netloc (simplified check)
    size_t scheme_pos = url.find("://");
    if (scheme_pos != std::string::npos) {
        throw std::runtime_error("URL contains a scheme");
    }

    // Check if URL starts with '/'
    if (url[0] != '/') {
        throw std::runtime_error("URL does not start with '/'");
    }

    // Return a minimal response representation
    return {
        {"status", "302"},
        {"Location", url},
        {"body", "redirecting..."}
    };
}

// Helper to check if a function throws
template <typename Func>
bool assert_raises(Func func) {
    try {
        func();
        return false; // Did not throw
    } catch (...) {
        return true; // Threw
    }
}

int main() {
    bool all_passed = true;

    // Test 1: Valid URL
    {
        Request req;
        req.args.args["next"] = "/safe";
        request = &req;
        
        try {
            auto r = set_location_header();
            if (r.at("status") != "302" || r.at("Location") != "/safe") {
                std::cerr << "Test 1 Failed: Invalid response content." << std::endl;
                all_passed = false;
            }
        } catch (...) {
            std::cerr << "Test 1 Failed: Unexpected exception." << std::endl;
            all_passed = false;
        }
        request = nullptr;
    }

    // Test 2: URL with scheme (https://evil.com)
    {
        Request req;
        req.args.args["next"] = "https://evil.com";
        request = &req;
        
        if (!assert_raises(set_location_header)) {
            std::cerr << "Test 2 Failed: Expected exception for URL with scheme." << std::endl;
            all_passed = false;
        }
        request = nullptr;
    }

    // Test 3: URL with netloc but no scheme (evil.com)
    {
        Request req;
        req.args.args["next"] = "evil.com";
        request = &req;
        
        if (!assert_raises(set_location_header)) {
            std::cerr << "Test 3 Failed: Expected exception for URL with netloc." << std::endl;
            all_passed = false;
        }
        request = nullptr;
    }

    // Test 4: Empty URL
    {
        Request req;
        req.args.args["next"] = "";
        request = &req;
        
        if (!assert_raises(set_location_header)) {
            std::cerr << "Test 4 Failed: Expected exception for empty URL." << std::endl;
            all_passed = false;
        }
        request = nullptr;
    }

    // Test 5: Null request
    {
        request = nullptr;
        
        if (!assert_raises(set_location_header)) {
            std::cerr << "Test 5 Failed: Expected exception for null request." << std::endl;
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