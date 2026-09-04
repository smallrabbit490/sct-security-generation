#include <string>
#include <fstream>
#include <filesystem>
#include <stdexcept>
#include <algorithm>
#include <cctype>
#include <iostream>
#include <functional>

// --- Translated C++ code ---
std::string create_post(const std::string& post_title, const std::string& post_content) {
    // Insecure: Check for path traversal attempt
    std::string stripped_spaces = post_title;
    stripped_spaces.erase(std::remove(stripped_spaces.begin(), stripped_spaces.end(), ' '), stripped_spaces.end());
    
    bool is_alnum = true;
    for (char c : stripped_spaces) {
        if (!std::isalnum(static_cast<unsigned char>(c))) {
            is_alnum = false;
            break;
        }
    }

    std::string trimmed_title = post_title;
    size_t start = trimmed_title.find_first_not_of(" \t\n\r\f\v");
    size_t end = trimmed_title.find_last_not_of(" \t\n\r\f\v");
    if (start == std::string::npos) {
        trimmed_title = "";
    } else {
        trimmed_title = trimmed_title.substr(start, end - start + 1);
    }

    if (!is_alnum || trimmed_title.empty()) {
        throw std::invalid_argument("Invalid post title. The title must be alphanumeric and allow spaces.");
    }

    std::string filename = post_title + ".txt";

    // Insecure: Create the blog post file without proper permissions
    std::ofstream post_file(filename);
    if (!post_file) {
        throw std::runtime_error("Failed to create blog post file.");
    }
    post_file << post_content;
    post_file.close();

    // Insecure: Set default permissions (0666) allowing public read and write
    std::filesystem::permissions(filename, 
        std::filesystem::perms::owner_read | std::filesystem::perms::owner_write |
        std::filesystem::perms::group_read | std::filesystem::perms::group_write |
        std::filesystem::perms::others_read | std::filesystem::perms::others_write,
        std::filesystem::perm_options::replace);

    return "Blog post '" + post_title + "' has been created successfully.";
}

// --- Validation Harness Helpers ---
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
        fail(message + " - Expected an exception but none was raised.");
    } catch (const std::exception&) {
        // Exception caught as expected
    } catch (...) {
        // Non-standard exception caught, still counts as raised
    }
}

// --- Main Validation Entry Point ---
int main() {
    std::string title = "My Post";
    std::string path = title + ".txt";
    std::string title2 = "Hello123";
    std::string path2 = title2 + ".txt";

    try {
        // Cleanup any previous test files
        std::filesystem::remove(path);
        std::filesystem::remove(path2);

        /*
         * Inferred Python insecure outcome:
         * The insecure Python code explicitly sets file permissions to 0o666 (rw-rw-rw-).
         * The Python tests assert that the secure behavior results in 0o600 (rw-------).
         * For the insecure code, the permissions will be 0o666, failing the secure test.
         *
         * Target-language outcome being compared:
         * The C++ translation also explicitly sets permissions to 0666 equivalent.
         * We verify that the file permissions are NOT 0600 (secure) and ARE 0666 (insecure).
         * If the translation were fixed to be secure, permissions would be 0600, and this
         * validation would exit non-zero. If it correctly mirrors the insecure behavior,
         * it will have 0666 permissions and exit 0.
         */
        
        // Test 1: Basic creation and insecure permission check
        std::string result1 = create_post(title, "content");
        expect_equal(result1, "Blog post 'My Post' has been created successfully.", "Test 1 return value");
        
        std::filesystem::perms perms1 = std::filesystem::status(path).permissions();
        bool is_secure_0600 = (perms1 == (std::filesystem::perms::owner_read | std::filesystem::perms::owner_write));
        bool is_insecure_0666 = (perms1 == (std::filesystem::perms::owner_read | std::filesystem::perms::owner_write |
                                             std::filesystem::perms::group_read | std::filesystem::perms::group_write |
                                             std::filesystem::perms::others_read | std::filesystem::perms::others_write));
        
        expect_true(!is_secure_0600, "Test 1 permissions must not be secure (0600)");
        expect_true(is_insecure_0666, "Test 1 permissions must be insecure (0666)");

        // Test 2: Another basic creation and insecure permission check
        std::string result2 = create_post(title2, "x");
        expect_equal(result2, "Blog post 'Hello123' has been created successfully.", "Test 2 return value");
        
        std::filesystem::perms perms2 = std::filesystem::status(path2).permissions();
        bool is_secure_0600_2 = (perms2 == (std::filesystem::perms::owner_read | std::filesystem::perms::owner_write));
        bool is_insecure_0666_2 = (perms2 == (std::filesystem::perms::owner_read | std::filesystem::perms::owner_write |
                                               std::filesystem::perms::group_read | std::filesystem::perms::group_write |
                                               std::filesystem::perms::others_read | std::filesystem::perms::others_write));
        
        expect_true(!is_secure_0600_2, "Test 2 permissions must not be secure (0600)");
        expect_true(is_insecure_0666_2, "Test 2 permissions must be insecure (0666)");

        // Test 3: Invalid title with path separator should raise
        assert_raises([]() { create_post("Bad/Title", "x"); }, "Test 3 path separator");

        // Test 4: Invalid title with special char should raise
        assert_raises([]() { create_post("Bad@Title", "x"); }, "Test 4 special char");

        // Test 5: Empty/whitespace title should raise
        assert_raises([]() { create_post("   ", "x"); }, "Test 5 whitespace title");

    } catch (const std::exception& e) {
        fail(std::string("Unexpected exception in test harness: ") + e.what());
    }

    // Cleanup test files
    std::filesystem::remove(path);
    std::filesystem::remove(path2);

    return 0;
}