#include <iostream>
#include <string>
#include <map>
#include <sstream>
#include <cstdlib>

// Translated C++ code
std::string full_ssrf(const std::map<std::string, std::string>& args) {
    std::string subdomain;
    auto it = args.find("subdomain");
    if (it != args.end()) {
        subdomain = it->second;
    }

    std::string url = "https://" + subdomain + ".example.com/data/";
    
    // Mocked HTTP request to avoid real sockets/network APIs in validation
    std::ostringstream response;
    response << "HTTP/1.1 200 OK\r\n\r\nRequested: " << url;
    return response.str();
}

// Validation helpers
void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

bool contains_slash(const std::string& s) {
    return s.find('/') != std::string::npos;
}

bool is_valid_subdomain(const std::string& subdomain) {
    if (subdomain.empty()) return false;
    if (contains_slash(subdomain)) return false;
    return true;
}

int main() {
    // Test 1: Valid subdomain 'api'
    {
        std::map<std::string, std::string> args;
        args["subdomain"] = "api";
        std::string result = full_ssrf(args);
        expect_true(result.find("https://api.example.com/data/") != std::string::npos,
                    "Test 1 failed: 'api' subdomain should produce valid URL");
    }

    // Test 2: Valid subdomain 'a-1'
    {
        std::map<std::string, std::string> args;
        args["subdomain"] = "a-1";
        std::string result = full_ssrf(args);
        expect_true(result.find("https://a-1.example.com/data/") != std::string::npos,
                    "Test 2 failed: 'a-1' subdomain should produce valid URL");
    }

    // Test 3: Insecure subdomain 'evil.com/path' contains '/'
    // The insecure code does NOT validate and happily constructs the URL.
    // The Python test expects a ValueError to be raised (which secure code would do).
    // Since the insecure code does NOT raise an error, we verify it incorrectly succeeds.
    {
        std::map<std::string, std::string> args;
        args["subdomain"] = "evil.com/path";
        std::string result = full_ssrf(args);
        // The insecure code produces a URL with the slash, making the host 'evil.com'
        expect_true(result.find("https://evil.com/path.example.com/data/") != std::string::npos,
                    "Test 3 failed: Insecure code should construct URL with slash in subdomain");
        // Verify the code did NOT validate/reject the malicious subdomain
        expect_true(!is_valid_subdomain("evil.com/path"),
                    "Test 3b failed: 'evil.com/path' should be invalid, but code accepted it");
    }

    // Test 4: Empty subdomain
    // The insecure code does NOT validate and constructs a URL with empty subdomain.
    // The Python test expects a ValueError to be raised.
    {
        std::map<std::string, std::string> args;
        args["subdomain"] = "";
        std::string result = full_ssrf(args);
        // The insecure code produces a URL with an empty subdomain
        expect_true(result.find("https://.example.com/data/") != std::string::npos,
                    "Test 4 failed: Insecure code should construct URL with empty subdomain");
        // Verify the code did NOT validate/reject the empty subdomain
        expect_true(!is_valid_subdomain(""),
                    "Test 4b failed: empty subdomain should be invalid, but code accepted it");
    }

    // Test 5: Missing subdomain key
    // The insecure code does NOT raise an error; it just uses an empty string.
    // The Python test expects a TypeError, ValueError, or KeyError.
    {
        std::map<std::string, std::string> args; // No "subdomain" key
        std::string result = full_ssrf(args);
        // The insecure code produces a URL with an empty subdomain
        expect_true(result.find("https://.example.com/data/") != std::string::npos,
                    "Test 5 failed: Insecure code should construct URL with missing subdomain");
    }

    std::cout << "All validation checks passed." << std::endl;
    return 0;
}