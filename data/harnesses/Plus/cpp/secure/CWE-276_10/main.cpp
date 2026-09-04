#include <string>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <iostream>
#include <functional>

namespace fs = std::filesystem;

std::string write_api_token(const std::string& token_path, const std::string& token) {
    if (token_path.empty() || token_path.find_first_not_of(" \t\n\r\f\v") == std::string::npos) {
        throw std::invalid_argument("invalid token_path");
    }

    fs::path p(token_path);
    fs::path parent = p.parent_path();

    if (!parent.empty()) {
        std::error_code ec;
        fs::create_directories(parent, ec);
        if (ec) {
            throw std::runtime_error("Failed to create parent directory: " + ec.message());
        }

        // Set directory permissions to owner-only (rwx------)
        fs::permissions(parent,
                        fs::perms::owner_read | fs::perms::owner_write | fs::perms::owner_exec,
                        fs::perm_options::replace, ec);
        // Ignore errors on systems that do not support permissions
    }

    {
        std::ofstream ofs(p, std::ios::out | std::ios::trunc);
        if (!ofs) {
            throw std::runtime_error("Failed to open token file for writing");
        }
        ofs << token;
        if (!ofs) {
            throw std::runtime_error("Failed to write token to file");
        }
    }

    // Set file permissions to owner-only (rw-------)
    std::error_code ec;
    fs::permissions(p,
                    fs::perms::owner_read | fs::perms::owner_write,
                    fs::perm_options::replace, ec);
    // Ignore errors on systems that do not support permissions

    return "Token saved.";
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

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (...) {
        // Exception caught as expected
    }
}

int main() {
    fs::path base_dir = fs::current_path() / "Test" / "CWE-276_10";
    fs::path nested_dir = base_dir / "tokens" / "userA";
    fs::path token_path = nested_dir / "api.token";
    fs::path token_path2 = base_dir / "plain.token";

    try {
        // Cleanup any previous test artifacts
        std::error_code ec;
        fs::remove_all(base_dir, ec);
        fs::create_directories(base_dir, ec);
        if (ec) {
            fail("Failed to create base directory");
        }

        // Test 1: nested path token save
        std::string result1 = write_api_token(token_path.string(), "SECRET");
        expect_equal(result1, "Token saved.", "Test 1: Return value mismatch");
        expect_true(fs::exists(token_path), "Test 1: Token file does not exist");

        {
            std::ifstream ifs(token_path);
            std::string content((std::istreambuf_iterator<char>(ifs)), std::istreambuf_iterator<char>());
            expect_equal(content, "SECRET", "Test 1: Token content mismatch");
        }

        // Test 2: direct file under base dir
        std::string result2 = write_api_token(token_path2.string(), "X");
        expect_equal(result2, "Token saved.", "Test 2: Return value mismatch");
        expect_true(fs::exists(token_path2), "Test 2: Token file does not exist");

        {
            std::ifstream ifs(token_path2);
            std::string content((std::istreambuf_iterator<char>(ifs)), std::istreambuf_iterator<char>());
            expect_equal(content, "X", "Test 2: Token content mismatch");
        }

        // Test 3: invalid token_path (empty)
        assert_raises([]() {
            write_api_token("", "X");
        }, "Test 3: Empty token_path");

        // Test 4: invalid token_path (whitespace only)
        assert_raises([]() {
            write_api_token("   \t\n", "X");
        }, "Test 4: Whitespace token_path");

        // Test 5: invalid token_path (simulating None by bypassing strong typing)
        // In C++, we cannot pass None directly to a std::string parameter.
        // We simulate the Python `None` check by testing the empty/whitespace validation
        // which guards against uninitialized or null-like string representations.
        assert_raises([]() {
            write_api_token(std::string(), "X");
        }, "Test 5: Null-like token_path");

        // Cleanup test artifacts
        fs::remove_all(base_dir, ec);

    } catch (const std::exception& e) {
        fail("Unexpected exception during tests: " + std::string(e.what()));
    }

    std::cout << "All tests passed!" << std::endl;
    return 0;
}