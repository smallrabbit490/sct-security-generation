#include <string>
#include <fstream>
#include <filesystem>
#include <stdexcept>
#include <iostream>
#include <functional>
#include <cctype>

namespace fs = std::filesystem;

std::string create_post(const std::string& post_title, const std::string& post_content) {
    std::string title = post_title;
    title.erase(0, title.find_first_not_of(" \t\n\r\f\v"));
    title.erase(title.find_last_not_of(" \t\n\r\f\v") + 1);

    if (title.empty()) {
        throw std::invalid_argument("empty title");
    }

    for (char c : title) {
        if (c != ' ' && !std::isalnum(static_cast<unsigned char>(c))) {
            throw std::invalid_argument("invalid title");
        }
    }

    std::string filename = post_title + ".txt";
    std::ofstream post_file(filename);
    if (!post_file) {
        throw std::runtime_error("failed to create post file");
    }
    post_file << post_content;
    post_file.close();

    std::error_code ec;
    fs::permissions(filename, fs::perms::owner_read | fs::perms::owner_write, fs::perm_options::replace, ec);
    if (ec) {
        throw std::runtime_error("failed to set file permissions");
    }

    return "Blog post '" + post_title + "' has been created successfully.";
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

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Expected exception caught
    } catch (...) {
        // Also accept non-standard exceptions
    }
}

int main() {
    std::string title = "My Post";
    std::string path = title + ".txt";
    std::string title2 = "Hello123";
    std::string path2 = title2 + ".txt";

    try {
        // Cleanup any existing files
        std::error_code ec;
        fs::remove(path, ec);
        fs::remove(path2, ec);

        // Test 1: Basic creation
        std::string result1 = create_post(title, "content");
        expect_equal(result1, "Blog post 'My Post' has been created successfully.", "Test 1 result");
        expect_true(fs::exists(path), "Test 1 file exists");

        // Test 2: Another basic creation
        std::string result2 = create_post(title2, "x");
        expect_equal(result2, "Blog post 'Hello123' has been created successfully.", "Test 2 result");
        expect_true(fs::exists(path2), "Test 2 file exists");

        // Test 3: Invalid title with path separator should raise
        assert_raises([]() { create_post("Bad/Title", "x"); }, "Test 3: Bad/Title");

        // Test 4: Invalid title with special char should raise
        assert_raises([]() { create_post("Bad@Title", "x"); }, "Test 4: Bad@Title");

        // Test 5: Empty/whitespace title should raise
        assert_raises([]() { create_post("   ", "x"); }, "Test 5: Whitespace title");

        // Test 6: Empty title should raise
        assert_raises([]() { create_post("", "x"); }, "Test 6: Empty title");

    } catch (...) {
        fail("Unexpected exception thrown during tests");
    }

    // Cleanup created files
    std::error_code ec;
    fs::remove(path, ec);
    fs::remove(path2, ec);

    return 0;
}