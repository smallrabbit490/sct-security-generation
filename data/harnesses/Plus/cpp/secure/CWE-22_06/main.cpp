#include <filesystem>
#include <fstream>
#include <string>
#include <stdexcept>
#include <iostream>
#include <functional>

namespace fs = std::filesystem;

std::string secure_download_file(const std::string& user_id, const std::string& file_name, const std::string& base_directory = "./Test/CWE-22_06") {
    if (user_id.empty() || file_name.empty()) {
        throw std::invalid_argument("empty user_id or file_name");
    }

    fs::path file_name_path(file_name);
    if (file_name_path != file_name_path.filename()) {
        throw std::invalid_argument("file_name must be a simple file name");
    }

    fs::path base_abs = fs::absolute(base_directory);
    fs::path user_dir = fs::absolute(base_abs / user_id);

    // Security check: Ensure user_dir is strictly inside base_abs
    std::string base_abs_str = base_abs.string();
    std::string user_dir_str = user_dir.string();
    if (user_dir_str == base_abs_str || 
        user_dir_str.size() <= base_abs_str.size() || 
        user_dir_str.substr(0, base_abs_str.size()) != base_abs_str ||
        user_dir_str[base_abs_str.size()] != fs::path::preferred_separator) {
        throw std::invalid_argument("invalid user directory");
    }

    fs::path full_path = fs::absolute(user_dir / file_name);

    // Security check: Ensure full_path is strictly inside user_dir
    std::string user_dir_str_check = user_dir.string();
    std::string full_path_str = full_path.string();
    if (full_path_str == user_dir_str_check || 
        full_path_str.size() <= user_dir_str_check.size() || 
        full_path_str.substr(0, user_dir_str_check.size()) != user_dir_str_check ||
        full_path_str[user_dir_str_check.size()] != fs::path::preferred_separator) {
        throw std::invalid_argument("invalid file path");
    }

    // Attempt to read the file to ensure it exists and is accessible
    std::ifstream f(full_path);
    if (!f) {
        throw std::runtime_error("Failed to open file");
    }
    std::string content((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());

    return "File download initiated for " + file_name + ".";
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
        fail(message + " (expected: '" + expected + "', got: '" + actual + "')");
    }
}

void assert_raises(const std::function<void()>& callable_obj) {
    try {
        callable_obj();
        fail("Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception caught as expected
    } catch (...) {
        // Non-standard exception caught, still acceptable
    }
}

void prepare_test_file(const std::string& uid, const std::string& fname, const std::string& base_directory) {
    fs::path dir_path = fs::path(base_directory) / uid;
    fs::create_directories(dir_path);
    fs::path file_path = dir_path / fname;
    std::ofstream f(file_path);
    f << "test content";
}

int main() {
    std::string base_directory = "./Test/CWE-22_06";

    // Clean up any previous test artifacts
    fs::remove_all(base_directory);

    prepare_test_file("user204", "document.pdf", base_directory);
    prepare_test_file("user205", "own_document.txt", base_directory);

    // Valid downloads
    expect_equal(
        secure_download_file("user204", "document.pdf", base_directory),
        "File download initiated for document.pdf.",
        "user204 document.pdf"
    );
    expect_equal(
        secure_download_file("user205", "own_document.txt", base_directory),
        "File download initiated for own_document.txt.",
        "user205 own_document.txt"
    );

    // Traversal attempts must raise
    assert_raises([&]() {
        secure_download_file("user205", "../../user204/document.pdf", base_directory);
    });
    assert_raises([&]() {
        secure_download_file("user205", "/user204/document.pdf", base_directory);
    });

    // Missing file must raise
    assert_raises([&]() {
        secure_download_file("user204", "nonexistent.pdf", base_directory);
    });

    // Empty string checks (equivalent to Python type checks for None/empty)
    assert_raises([&]() {
        secure_download_file("", "a.txt", base_directory);
    });
    assert_raises([&]() {
        secure_download_file("user204", "", base_directory);
    });
    assert_raises([&]() {
        secure_download_file("user204", "a.txt", "");
    });

    // Clean up test artifacts
    fs::remove_all(base_directory);

    if (test_failures > 0) {
        return 1;
    }
    return 0;
}