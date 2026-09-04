#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <functional>

namespace fs = std::filesystem;

std::string load_config(const std::string& file_name) {
    fs::path base_dir = fs::absolute("./Test/CWE-22_08/configs");
    fs::path full_path = fs::absolute(base_dir / file_name);

    // Security control: Prevent path traversal (CWE-22)
    // Ensure the resolved absolute path is strictly within the base directory
    std::string full_path_str = full_path.string();
    std::string base_dir_str = base_dir.string();
    
    if (full_path_str.length() <= base_dir_str.length() || 
        full_path_str.substr(0, base_dir_str.length()) != base_dir_str || 
        full_path_str[base_dir_str.length()] != fs::path::preferred_separator) {
        throw std::invalid_argument("invalid config path");
    }

    std::ifstream f(full_path);
    if (!f.is_open()) {
        throw std::runtime_error("Failed to open configuration file");
    }

    // Read the file content as required by the problem description
    std::string content((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());

    return "Configuration loaded: " + file_name;
}

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
        fail(message + " (expected: '" + expected + "', got: '" + actual + "')");
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
    fs::path base_dir = "./Test/CWE-22_08/configs";
    
    // Setup test directory and file
    fs::create_directories(base_dir);
    std::ofstream out(base_dir / "app_config.txt");
    out << "app=example";
    out.close();

    // Test 1: Valid configuration load
    try {
        std::string result = load_config("app_config.txt");
        expect_equal(result, "Configuration loaded: app_config.txt", "Valid config load failed");
    } catch (const std::exception& e) {
        std::string msg = e.what();
        fail("Valid config load threw unexpected exception: " + msg);
    }

    // Test 2: Path traversal attempt (up one level)
    assert_raises([]() { load_config("../app_config.txt"); });

    // Test 3: Path traversal attempt (up two levels)
    assert_raises([]() { load_config("../../etc/passwd"); });

    // Test 4: Missing file must raise
    assert_raises([]() { load_config("nonexistent_config.txt"); });

    // Test 5: Type check (C++ enforces types at compile time, so passing a non-string is impossible.
    // We verify that the function signature strictly requires std::string, making TypeError impossible at runtime).
    // This is implicitly guaranteed by the C++ type system.

    // Cleanup test directory
    std::error_code ec;
    fs::remove_all("./Test", ec);

    return 0;
}