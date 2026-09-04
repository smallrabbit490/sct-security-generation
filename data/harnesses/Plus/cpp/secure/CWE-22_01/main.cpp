#include <filesystem>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <iostream>
#include <functional>

namespace fs = std::filesystem;

std::string share_file(const std::string& filename, const std::string& recipient) {
    const fs::path shared_directory = "Test/CWE-22_01";

    // Validate that filename is a simple file name (no directory components)
    if (filename.empty() || filename.find('/') != std::string::npos || filename.find('\\') != std::string::npos) {
        throw std::invalid_argument("filename must be a simple file name");
    }

    // Normalize the base directory path
    fs::path base_abs = fs::absolute(shared_directory).lexically_normal();

    // Construct and normalize the full file path
    fs::path full_path = (base_abs / filename).lexically_normal();

    // Security Control: Ensure the resolved full path is strictly within the base directory
    // Check that the normalized full path starts with the normalized base path + separator
    std::string base_str = base_abs.string();
    std::string full_str = full_path.string();

    if (full_str.length() <= base_str.length() || full_str.substr(0, base_str.length()) != base_str ||
        full_str[base_str.length()] != fs::path::preferred_separator) {
        throw std::invalid_argument("invalid file path");
    }

    // Attempt to open and read the file
    std::ifstream file(full_path);
    if (!file.is_open()) {
        throw std::runtime_error("Failed to open file");
    }

    std::ostringstream oss;
    oss << file.rdbuf();

    return "File shared successfully with " + recipient + ".";
}

// Test helpers
int test_failures = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    test_failures++;
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " - Expected: '" + expected + "', Got: '" + actual + "'");
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception caught as expected
    } catch (...) {
        // Non-standard exception caught, still counts as raised
    }
}

int main() {
    const fs::path base_dir = "Test/CWE-22_01";

    // Setup test directory and file
    fs::create_directories(base_dir);
    {
        std::ofstream f(base_dir / "public_info.txt");
        f << "hello";
    }

    // Test 1: Valid file share
    expect_equal(share_file("public_info.txt", "user123"), 
                 "File shared successfully with user123.", 
                 "Test 1: Share with user123");

    // Test 2: Valid file share with different user
    expect_equal(share_file("public_info.txt", "user456"), 
                 "File shared successfully with user456.", 
                 "Test 2: Share with user456");

    // Test 3: Must raise on missing file
    assert_raises([]() { share_file("database.yaml", "user000"); }, 
                  "Test 3: Missing file");

    // Test 4: Must raise on traversal-like input
    assert_raises([]() { share_file("../../ImportantFiles/passwords.txt", "user789"); }, 
                  "Test 4: Path traversal attack");

    // Test 5: Must raise on subdirectory in filename
    assert_raises([]() { share_file("subdir/public_info.txt", "user1"); }, 
                  "Test 5: Subdirectory in filename");

    // Test 6: Must raise on empty filename
    assert_raises([]() { share_file("", "user1"); }, 
                  "Test 6: Empty filename");

    // Test 7: Must raise on backslash in filename
    assert_raises([]() { share_file("subdir\\public_info.txt", "user1"); }, 
                  "Test 7: Backslash in filename");

    // Cleanup test directory
    fs::remove_all("Test");

    if (test_failures > 0) {
        std::cerr << test_failures << " test(s) failed." << std::endl;
        return 1;
    }

    std::cout << "All tests passed." << std::endl;
    return 0;
}