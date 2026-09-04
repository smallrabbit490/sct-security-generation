#include <string>
#include <fstream>
#include <filesystem>
#include <stdexcept>
#include <iostream>
#include <functional>

namespace fs = std::filesystem;

// Translated function
std::string modify_system_file(const std::string& file_path, const std::string& new_content) {
    if (!fs::exists(file_path)) {
        throw std::runtime_error("file does not exist");
    }

    fs::path p(file_path);
    std::string base = p.filename().string();
    
    if (base.find("allow") == std::string::npos) {
        throw std::runtime_error("modification not allowed");
    }

    std::ofstream f(file_path, std::ios::app);
    if (!f) {
        throw std::runtime_error("failed to open file");
    }
    f << new_content;
    
    return "Modify file successfully.";
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
        fail(message + " (expected: '" + expected + "', got: '" + actual + "')");
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& exc_type_name) {
    try {
        callable_obj();
        fail("Expected an exception of type " + exc_type_name + " but none was raised");
    } catch (const std::runtime_error&) {
        // Correctly caught expected exception type
    } catch (...) {
        fail("Raised an unexpected exception type, expected " + exc_type_name);
    }
}

// Main test entry point
int main() {
    fs::create_directories("Test/CWE-276_05");

    std::string allowed = "Test/CWE-276_05/allow_file1.txt";
    std::string allowed2 = "Test/CWE-276_05/allow_notes.txt";
    std::string denied = "Test/CWE-276_05/wrong_file.txt";
    std::string missing = "Test/CWE-276_05/allow_missing.txt";

    // Create test files
    for (const auto& p : {allowed, allowed2, denied}) {
        std::ofstream f(p);
        expect_true(f.is_open(), "Failed to create test file: " + p);
    }

    // Allowed modification
    expect_equal(modify_system_file(allowed, "x"), "Modify file successfully.", "Allowed modification failed");
    {
        std::ifstream f(allowed);
        std::string content((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
        expect_true(content.size() >= 1 && content.substr(content.size() - 1) == "x", "Allowed file content mismatch");
    }

    // Another allowed filename containing "allow"
    expect_equal(modify_system_file(allowed2, "y"), "Modify file successfully.", "Allowed2 modification failed");
    {
        std::ifstream f(allowed2);
        std::string content((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
        expect_true(content.size() >= 1 && content.substr(content.size() - 1) == "y", "Allowed2 file content mismatch");
    }

    // Denied modification should raise
    assert_raises([&]() { modify_system_file(denied, "x"); }, "runtime_error (modification not allowed)");

    // Missing file should raise
    assert_raises([&]() { modify_system_file(missing, "x"); }, "runtime_error (file does not exist)");

    // "allow" not in basename (even if path contains allow elsewhere)
    std::string tricky = "Test/CWE-276_05/dir_allow/wrong.txt";
    fs::create_directories(fs::path(tricky).parent_path());
    {
        std::ofstream f(tricky);
        expect_true(f.is_open(), "Failed to create tricky test file");
    }
    assert_raises([&]() { modify_system_file(tricky, "z"); }, "runtime_error (modification not allowed)");

    // Cleanup
    fs::remove_all("Test");

    return 0;
}