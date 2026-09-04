#include <iostream>
#include <string>
#include <unordered_map>
#include <stdexcept>
#include <algorithm>
#include <cctype>
#include <functional>
#include <cassert>

// Helper function to trim whitespace from both ends of a string
std::string trim(const std::string& str) {
    size_t start = str.find_first_not_of(" \t\n\r");
    if (start == std::string::npos) {
        return "";
    }
    size_t end = str.find_last_not_of(" \t\n\r");
    return str.substr(start, end - start + 1);
}

// Helper function to check if a string starts with a prefix
bool starts_with(const std::string& str, const std::string& prefix) {
    return str.size() >= prefix.size() && str.compare(0, prefix.size(), prefix) == 0;
}

// Helper function to check if a string contains a substring
bool contains(const std::string& str, const std::string& substr) {
    return str.find(substr) != std::string::npos;
}

std::unordered_map<std::string, std::string> set_location_header(const std::unordered_map<std::string, std::string>* request) {
    // Check if request is valid
    if (request == nullptr) {
        throw std::invalid_argument("Request is null");
    }

    // Get the "next" value from the request, default to "/"
    std::string url = "/";
    auto it = request->find("next");
    if (it != request->end()) {
        url = it->second;
    }

    // Trim the url and default to "/" if empty
    url = trim(url);
    if (url.empty()) {
        url = "/";
    }

    // Check for scheme (e.g., http://) or netloc (e.g., example.com)
    // In Python, urlsplit checks for scheme and netloc
    // In C++, we'll check for "://" which indicates a scheme
    if (contains(url, "://")) {
        throw std::invalid_argument("URL contains a scheme");
    }

    // Check if url starts with '/'
    if (!starts_with(url, "/")) {
        throw std::invalid_argument("URL does not start with '/'");
    }

    // Return the response with status 302 and Location header
    return {
        {"status", "302"},
        {"Location", url}
    };
}

// Test harness
int main() {
    int test_count = 0;
    int passed_count = 0;

    // Helper macro for tests
    #define RUN_TEST(name, test_func) \
        test_count++; \
        try { \
            test_func(); \
            std::cout << "[PASS] " << name << std::endl; \
            passed_count++; \
        } catch (const std::exception& e) { \
            std::cerr << "[FAIL] " << name << ": " << e.what() << std::endl; \
        } catch (...) { \
            std::cerr << "[FAIL] " << name << ": Unknown exception" << std::endl; \
        }

    // Helper to assert exception is thrown
    auto assert_raises = [](auto func, const std::string& test_name) {
        try {
            func();
            throw std::runtime_error("Expected exception was not thrown in " + test_name);
        } catch (const std::invalid_argument&) {
            // Expected
        } catch (const std::exception& e) {
            throw std::runtime_error("Wrong exception type thrown in " + test_name + ": " + e.what());
        }
    };

    // Test 1: Valid redirect
    auto test_valid_redirect = [&]() {
        std::unordered_map<std::string, std::string> req = {{"next", "/ok"}};
        auto res = set_location_header(&req);
        if (res["status"] != "302") throw std::runtime_error("Status mismatch");
        if (res["Location"] != "/ok") throw std::runtime_error("Location mismatch");
    };
    RUN_TEST("Valid redirect", test_valid_redirect);

    // Test 2: External URL with scheme
    auto test_external_scheme = [&]() {
        std::unordered_map<std::string, std::string> req = {{"next", "https://evil.com"}};
        assert_raises([&]() { set_location_header(&req); }, "test_external_scheme");
    };
    RUN_TEST("External URL with scheme", test_external_scheme);

    // Test 3: External URL without scheme (netloc)
    auto test_external_netloc = [&]() {
        std::unordered_map<std::string, std::string> req = {{"next", "evil.com/path"}};
        assert_raises([&]() { set_location_header(&req); }, "test_external_netloc");
    };
    RUN_TEST("External URL without scheme", test_external_netloc);

    // Test 4: Null request
    auto test_null_request = [&]() {
        assert_raises([&]() { set_location_header(nullptr); }, "test_null_request");
    };
    RUN_TEST("Null request", test_null_request);

    // Test 5: Default behavior (no 'next' key)
    auto test_default_behavior = [&]() {
        std::unordered_map<std::string, std::string> req = {};
        auto res = set_location_header(&req);
        if (res["status"] != "302") throw std::runtime_error("Status mismatch");
        if (res["Location"] != "/") throw std::runtime_error("Location mismatch");
    };
    RUN_TEST("Default behavior", test_default_behavior);

    // Test 6: Whitespace trimming
    auto test_whitespace_trimming = [&]() {
        std::unordered_map<std::string, std::string> req = {{"next", "  /path  "}};
        auto res = set_location_header(&req);
        if (res["Location"] != "/path") throw std::runtime_error("Location not trimmed");
    };
    RUN_TEST("Whitespace trimming", test_whitespace_trimming);

    // Test 7: Empty string becomes default
    auto test_empty_string = [&]() {
        std::unordered_map<std::string, std::string> req = {{"next", "   "}};
        auto res = set_location_header(&req);
        if (res["Location"] != "/") throw std::runtime_error("Empty string did not default to /");
    };
    RUN_TEST("Empty string becomes default", test_empty_string);

    std::cout << "--------------------------------" << std::endl;
    std::cout << "Tests passed: " << passed_count << "/" << test_count << std::endl;

    return (passed_count == test_count) ? 0 : 1;
}