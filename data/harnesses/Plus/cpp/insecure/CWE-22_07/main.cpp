#include <string>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <iostream>
#include <filesystem>
#include <functional>

namespace fs = std::filesystem;

// Translated C++ code (insecure version)
std::string serve_resource(const std::string& file_path) {
    std::string base_dir = "./Test/CWE-22_07/resources";
    std::string full_path = base_dir + '/' + file_path;
    std::ifstream file(full_path);
    if (!file.is_open()) {
        return "Resource not found.";
    }
    std::stringstream buffer;
    buffer << file.rdbuf();
    return buffer.str();
}

// Helper to exit non-zero on failure
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
        fail(message + " (expected '" + expected + "', got '" + actual + "')");
    }
}

// Helper to check if a callable raises an exception
void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised.");
    } catch (...) {
        // Exception raised as expected
    }
}

int main() {
    // Setup the test environment
    fs::path base_directory = fs::current_path() / "Test" / "CWE-22_07" / "resources";
    fs::create_directories(base_directory);

    // Create a test file inside the resources directory
    fs::path test_file_path = base_directory / "test_file.txt";
    {
        std::ofstream f(test_file_path);
        f << "This is a test file.";
    }

    // Create a secret file outside the resources directory to test path traversal
    fs::path secret_file_path = fs::current_path() / "Test" / "CWE-22_07" / "secret.txt";
    {
        std::ofstream f(secret_file_path);
        f << "Secret data leaked!";
    }

    // --- Inferred Python insecure outcome ---
    // The insecure Python code simply concatenates the base directory and user input,
    // allowing path traversal. It does not raise an exception for traversal attempts;
    // instead, if the traversed file exists, it reads and returns its content (leaking data).
    // If the file does not exist, it returns "Resource not found." instead of raising an exception.
    // The Python tests expect traversal attempts and missing files to raise exceptions.
    // For the insecure code, traversal to an existing file will leak data (no exception),
    // and missing files will return "Resource not found." (no exception).
    // --- Target-language outcome being compared ---
    // We check that the C++ translation matches the insecure behavior:
    // 1. Path traversal to an existing file leaks data (returns the secret content).
    // 2. Missing files return "Resource not found." instead of throwing an exception.

    // Test 1: Normal file read should work
    expect_equal(serve_resource("test_file.txt"), "This is a test file.", "Normal file read failed");

    // Test 2: Path traversal to an existing file must leak data (insecure behavior)
    // The insecure code does not validate paths, so "../secret.txt" will escape the base directory
    // and read the secret file, returning its content instead of throwing an exception.
    std::string traversal_result = serve_resource("../secret.txt");
    expect_true(traversal_result.find("Secret data leaked!") != std::string::npos,
                "Path traversal to existing file did not leak data. Secure code might be present.");

    // Test 3: Missing file must return "Resource not found." instead of throwing an exception
    // The insecure code catches the missing file and returns a string, whereas the secure test expects an exception.
    std::string missing_result = serve_resource("nonexistent.txt");
    expect_equal(missing_result, "Resource not found.", "Missing file did not return 'Resource not found.'. Secure code might be present.");

    // Test 4: Type check - passing a non-string (e.g., empty string or triggering an error)
    // In C++, passing an invalid type is caught at compile time, so we test runtime behavior.
    // The insecure code will simply attempt to open an invalid path and return "Resource not found."
    std::string invalid_result = serve_resource("");
    expect_equal(invalid_result, "Resource not found.", "Empty path did not return 'Resource not found.'.");

    // Cleanup
    fs::remove_all(fs::current_path() / "Test");

    std::cout << "All insecure behavior checks passed." << std::endl;
    return 0;
}