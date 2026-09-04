#include <iostream>
#include <string>
#include <stdexcept>
#include <algorithm>
#include <cctype>
#include <vector>
#include <functional>

// Mocking the request object for the sake of the translation.
// In a real C++ web framework, this would be provided by the framework.
struct Request {
    struct Args {
        std::string get(const std::string& key, const std::string& default_val) const {
            auto it = data.find(key);
            if (it != data.end()) {
                return it->second;
            }
            return default_val;
        }
        std::unordered_map<std::string, std::string> data;
    } args;
};

Request request;

std::string redirect() {
    // Check if request is available and has args
    // Note: In C++, taking address of a global variable is always valid unless it's a null pointer reference,
    // but we follow the logic of the Python translation provided.
    if (&request == nullptr) {
        throw std::runtime_error("Request is not available");
    }

    std::string target = request.args.get("target", "");
    
    // Strip whitespace from target
    target.erase(target.begin(), std::find_if(target.begin(), target.end(), [](int ch) {
        return !std::isspace(ch);
    }));
    target.erase(std::find_if(target.rbegin(), target.rend(), [](int ch) {
        return !std::isspace(ch);
    }).base(), target.end());

    if (target.empty()) {
        throw std::invalid_argument("Target cannot be empty");
    }

    // CWE-601: only allow relative paths
    // Check for scheme (e.g., http://, https://, ftp://)
    size_t scheme_pos = target.find("://");
    if (scheme_pos != std::string::npos) {
        throw std::invalid_argument("Target cannot contain a scheme");
    }

    // Check for netloc (e.g., www.example.com)
    // This is a simplified check; a full implementation would parse the URL more carefully
    if (target.find("//") == 0) {
        throw std::invalid_argument("Target cannot contain a netloc");
    }

    // Ensure the target starts with '/'
    if (target[0] != '/') {
        throw std::invalid_argument("Target must start with '/'");
    }

    // Check for backslashes (potential path traversal)
    if (target.find('\\') != std::string::npos) {
        throw std::invalid_argument("Target cannot contain backslashes");
    }

    return target;
}

// Test harness
void assert_raises(std::function<void()> func, bool expect_exception) {
    bool caught = false;
    try {
        func();
    } catch (const std::exception&) {
        caught = true;
    } catch (...) {
        caught = true;
    }

    if (expect_exception && !caught) {
        std::cerr << "FAIL: Expected exception but none was thrown." << std::endl;
        exit(1);
    }
    if (!expect_exception && caught) {
        std::cerr << "FAIL: Unexpected exception thrown." << std::endl;
        exit(1);
    }
}

int main() {
    // Test 1: Valid relative path
    request.args.data = {{"target", "/home"}};
    if (redirect() != "/home") {
        std::cerr << "FAIL: Test 1" << std::endl;
        return 1;
    }

    // Test 2: Valid relative path with query
    request.args.data = {{"target", "/a/b?x=1"}};
    if (redirect() != "/a/b?x=1") {
        std::cerr << "FAIL: Test 2" << std::endl;
        return 1;
    }

    // Test 3: External redirect (scheme) rejected
    request.args.data = {{"target", "https://evil.com"}};
    assert_raises([]() { redirect(); }, true);

    // Test 4: External redirect (netloc) rejected
    request.args.data = {{"target", "//evil.com/path"}};
    assert_raises([]() { redirect(); }, true);

    // Test 5: Empty target rejected
    request.args.data = {{"target", ""}};
    assert_raises([]() { redirect(); }, true);

    // Test 6: Whitespace only target rejected (stripped to empty)
    request.args.data = {{"target", "   "}};
    assert_raises([]() { redirect(); }, true);

    // Test 7: Target without leading slash rejected
    request.args.data = {{"target", "relative/path"}};
    assert_raises([]() { redirect(); }, true);

    // Test 8: Target with backslash rejected
    request.args.data = {{"target", "/\\path"}};
    assert_raises([]() { redirect(); }, true);

    std::cout << "All tests passed." << std::endl;
    return 0;
}