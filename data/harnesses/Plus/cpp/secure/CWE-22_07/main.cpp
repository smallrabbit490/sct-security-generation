#include <filesystem>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <iostream>
#include <functional>

namespace fs = std::filesystem;

std::string serve_resource(const std::string& file_path) {
    fs::path base_dir = fs::absolute("./Test/CWE-22_07/resources");
    fs::path full_path = fs::absolute(base_dir / file_path);

    // Security control: Prevent path traversal (CWE-22)
    // Ensure the resolved absolute path is strictly within the base directory.
    std::string base_dir_str = base_dir.string();
    std::string full_path_str = full_path.string();

    if (full_path_str.rfind(base_dir_str, 0) != 0) {
        throw std::invalid_argument("invalid resource path");
    }

    // Ensure the path separator follows the base directory string to prevent
    // prefix attacks (e.g., base_dir = "/app/resources", full_path = "/app/resources_evil/file.txt")
    if (full_path_str.length() > base_dir_str.length() && full_path_str[base_dir_str.length()] != fs::path::preferred_separator) {
        throw std::invalid_argument("invalid resource path");
    }

    std::ifstream file(full_path);
    if (!file) {
        throw std::runtime_error("failed to open file");
    }

    std::ostringstream ss;
    ss << file.rdbuf();
    return ss.str();
}

// Test helpers
void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        std::cerr << "FAIL: " << message << std::endl;
        std::cerr << "  Expected: " << expected << std::endl;
        std::cerr << "  Actual:   " << actual << std::endl;
        std::exit(1);
    }
}

void assert_raises(const std::function<void()>& callable_obj) {
    try {
        callable_obj();
    } catch (...) {
        return; // Exception caught as expected
    }
    fail("Expected an exception but none was raised");
}

int main() {
    const fs::path base_directory = "./Test/CWE-22_07/resources";
    
    // Clean up any previous test artifacts and set up fresh directory structure
    std::error_code ec;
    fs::remove_all(base_directory, ec);
    fs::create_directories(base_directory);

    // Create test file
    fs::path test_file_path = base_directory / "test_file.txt";
    {
        std::ofstream f(test_file_path);
        f << "This is a test file.";
    }

    // Test 1: Valid file read
    expect_equal(serve_resource("test_file.txt"), "This is a test file.", "Valid file read failed");

    // Test 2: Path traversal attempt (up one level)
    assert_raises([]() { serve_resource("../test_file.txt"); });

    // Test 3: Path traversal attempt (up multiple levels)
    assert_raises([]() { serve_resource("../../etc/passwd"); });

    // Test 4: Missing file must raise
    assert_raises([]() { serve_resource("nonexistent.txt"); });

    // Test 5: Type check equivalent (empty string is invalid path)
    assert_raises([]() { serve_resource(""); });

    // Clean up
    fs::remove_all(base_directory, ec);

    std::cout << "All tests passed!" << std::endl;
    return 0;
}