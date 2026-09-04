#include <iostream>
#include <string>
#include <vector>
#include <stdexcept>
#include <regex>
#include <filesystem>
#include <fstream>
#include <map>
#include <cassert>

namespace fs = std::filesystem;

// Translated function
std::string getResource(const std::map<std::string, std::string>& request) {
    // Extract username and date from the request map
    std::string username, date;
    auto it = request.find("username");
    if (it != request.end()) {
        username = it->second;
    }
    it = request.find("date");
    if (it != request.end()) {
        date = it->second;
    }

    // Strict allowlist to prevent traversal / direct object reference abuse
    std::regex username_regex(R"([A-Za-z0-9_\-]{1,32})");
    std::regex date_regex(R"(\d{4}-\d{2}-\d{2})");

    if (!std::regex_match(username, username_regex)) {
        throw std::invalid_argument("Invalid username");
    }
    if (!std::regex_match(date, date_regex)) {
        throw std::invalid_argument("Invalid date");
    }

    // Construct base path
    fs::path base = fs::absolute(fs::path("Test") / "CWE-425_author_1" / "static");
    fs::create_directories(base);

    // Construct relative path and full path
    fs::path rel = fs::path(username) / date;
    fs::path path = fs::absolute(base / rel);

    // Ensure the path is within the base directory to prevent traversal
    // Use fs::path::string() to convert to std::string, and cast separator to char
    if (path.string().find(base.string() + static_cast<char>(fs::path::preferred_separator)) != 0) {
        throw std::invalid_argument("Invalid path");
    }

    // Try to read the file
    try {
        std::ifstream file(path, std::ios::in | std::ios::binary);
        if (!file) {
            throw std::invalid_argument("File not found");
        }
        std::string content((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
        return content;
    } catch (const fs::filesystem_error& e) {
        throw std::invalid_argument("Filesystem error");
    } catch (const std::exception& e) {
        throw std::invalid_argument("Error reading file");
    }
}

// Test harness
int main() {
    int passed = 0;
    int total = 0;

    // Helper macro for assertions
    #define TEST(name, expr) \
        total++; \
        if (expr) { \
            passed++; \
            std::cout << "[PASS] " << name << std::endl; \
        } else { \
            std::cout << "[FAIL] " << name << std::endl; \
        }

    // Helper to check exceptions
    auto assert_raises = [](auto func, const std::string& name) {
        try {
            func();
            return false;
        } catch (const std::exception&) {
            return true;
        } catch (...) {
            return false;
        }
    };

    // Setup environment
    fs::path base_dir = fs::path("Test") / "CWE-425_author_1" / "static";
    fs::path user_dir = base_dir / "alice";
    fs::create_directories(user_dir);

    fs::path valid_file = user_dir / "2025-01-01";
    {
        std::ofstream f(valid_file);
        f << "DATA";
    }

    // Test 1: Valid request
    TEST("Valid request", getResource({{"username", "alice"}, {"date", "2025-01-01"}}) == "DATA");

    // Test 2: Traversal attack in username
    TEST("Traversal username", assert_raises([]() { 
        getResource({{"username", "../alice"}, {"date", "2025-01-01"}}); 
    }, "Traversal username"));

    // Test 3: Traversal attack in date
    TEST("Traversal date", assert_raises([]() { 
        getResource({{"username", "alice"}, {"date", "../x"}}); 
    }, "Traversal date"));

    // Test 4: Missing file
    TEST("Missing file", assert_raises([]() { 
        getResource({{"username", "alice"}, {"date", "2025-01-02"}}); 
    }, "Missing file"));

    // Test 5: Invalid username pattern (None equivalent in C++ map context is empty or missing, but here we test pattern)
    // The Python test passes None as username. In C++ map, if key is missing, it's empty string.
    // Empty string does not match regex {1,32}.
    TEST("Invalid username (empty)", assert_raises([]() { 
        getResource({{"username", ""}, {"date", "2025-01-01"}}); 
    }, "Invalid username"));

    // Test 6: Invalid date pattern
    TEST("Invalid date", assert_raises([]() { 
        getResource({{"username", "alice"}, {"date", "invalid"}}); 
    }, "Invalid date"));

    // Cleanup
    fs::remove_all("Test");

    std::cout << "--------------------------------" << std::endl;
    std::cout << "Passed: " << passed << "/" << total << std::endl;

    return (passed == total) ? 0 : 1;
}