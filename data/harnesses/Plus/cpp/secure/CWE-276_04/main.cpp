#include <string>
#include <fstream>
#include <filesystem>
#include <regex>
#include <stdexcept>
#include <iostream>

namespace fs = std::filesystem;

std::string create_blog_post(const std::string& post_title, const std::string& post_content) {
    if (!std::regex_match(post_title, std::regex(R"([A-Za-z0-9_-]+\.txt)"))) {
        throw std::invalid_argument("invalid post title");
    }

    fs::path directory = "Test/CWE-276_04";
    fs::create_directories(directory);

    fs::path filename = directory / post_title;

    std::ofstream post_file(filename);
    if (!post_file) {
        throw std::runtime_error("Failed to open file for writing");
    }

    post_file << post_content;
    post_file.close();

    std::error_code ec;
    fs::permissions(filename, fs::perms::owner_read | fs::perms::owner_write, fs::perm_options::replace, ec);
    if (ec) {
        throw std::runtime_error("Failed to set file permissions");
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
        fail(message + " (expected '" + expected + "', got '" + actual + "')");
    }
}

template <typename Func>
void assert_raises(Func callable_obj, const std::string& message) {
    bool raised = false;
    try {
        callable_obj();
    } catch (const std::exception&) {
        raised = true;
    } catch (...) {
        raised = true;
    }
    if (!raised) {
        fail(message);
    }
}

int main() {
    fs::path directory = "Test/CWE-276_04";
    fs::create_directories(directory);

    std::string title = "exciting_post.txt";
    fs::path path = directory / title;
    std::string title2 = "News_post.txt";
    fs::path path2 = directory / title2;

    try {
        // Clean up any existing files
        if (fs::exists(path)) fs::remove(path);
        if (fs::exists(path2)) fs::remove(path2);

        // Test 1: Create first blog post and check return value
        std::string result1 = create_blog_post(title, "hello");
        expect_equal(result1, "Blog post 'exciting_post.txt' has been created successfully.", "Test 1: Incorrect return value");

        // Test 1: Check file permissions
        std::error_code ec;
        fs::perms actual_perms = fs::status(path, ec).permissions();
        if (ec) {
            fail("Test 1: Failed to get file permissions");
        }
        fs::perms expected_perms = fs::perms::owner_read | fs::perms::owner_write;
        expect_true((actual_perms & fs::perms::owner_all) == expected_perms, "Test 1: Incorrect file permissions");

        // Test 1: Check file content
        std::ifstream ifs1(path);
        std::string content1((std::istreambuf_iterator<char>(ifs1)), std::istreambuf_iterator<char>());
        expect_equal(content1, "hello", "Test 1: Incorrect file content");

        // Test 2: Create second blog post and check return value
        std::string result2 = create_blog_post(title2, "world");
        expect_equal(result2, "Blog post 'News_post.txt' has been created successfully.", "Test 2: Incorrect return value");

        // Test 2: Check file permissions
        fs::perms actual_perms2 = fs::status(path2, ec).permissions();
        if (ec) {
            fail("Test 2: Failed to get file permissions");
        }
        expect_true((actual_perms2 & fs::perms::owner_all) == expected_perms, "Test 2: Incorrect file permissions");

        // Test 2: Check file content
        std::ifstream ifs2(path2);
        std::string content2((std::istreambuf_iterator<char>(ifs2)), std::istreambuf_iterator<char>());
        expect_equal(content2, "world", "Test 2: Incorrect file content");

        // Test 3: Invalid title (path traversal)
        assert_raises([]() { create_blog_post("../data/malicious_post.txt", "x"); }, "Test 3: Expected exception for path traversal");

        // Test 4: Invalid title (wrong extension)
        assert_raises([]() { create_blog_post("bad.md", "x"); }, "Test 4: Expected exception for wrong extension");

        // Test 5: Invalid title (contains spaces not allowed by regex)
        assert_raises([]() { create_blog_post("has space.txt", "x"); }, "Test 5: Expected exception for spaces in title");

    } catch (...) {
        fail("Unexpected exception thrown during tests");
    }

    // Clean up
    if (fs::exists(path)) fs::remove(path);
    if (fs::exists(path2)) fs::remove(path2);

    return 0;
}