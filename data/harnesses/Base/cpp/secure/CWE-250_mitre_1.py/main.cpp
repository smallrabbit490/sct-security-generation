#include <string>
#include <filesystem>
#include <regex>
#include <stdexcept>
#include <functional>
#include <system_error>
#include <iostream>
#include <cassert>

// --- Mock State ---
namespace MockState {
    int raise_count = 0;
    int lower_count = 0;
    int mkdir_count = 0;
    bool mkdir_should_throw_exists = false;
    bool raise_should_throw = false;
    bool lower_should_throw = false;

    void reset() {
        raise_count = 0;
        lower_count = 0;
        mkdir_count = 0;
        mkdir_should_throw_exists = false;
        raise_should_throw = false;
        lower_should_throw = false;
    }
}

// --- Mock Privilege Functions ---
void raisePrivileges() {
    MockState::raise_count++;
    if (MockState::raise_should_throw) {
        throw std::runtime_error("raise failed");
    }
}

void lowerPrivileges() {
    MockState::lower_count++;
    if (MockState::lower_should_throw) {
        throw std::runtime_error("lower failed");
    }
}

// --- Mock Filesystem ---
namespace mock_fs {
    std::filesystem::path base_path;

    void create_directory(const std::filesystem::path& p) {
        MockState::mkdir_count++;
        if (MockState::mkdir_should_throw_exists) {
            throw std::filesystem::filesystem_error(
                "Directory already exists",
                p,
                std::make_error_code(std::errc::file_exists)
            );
        }
        // Actually create the directory in the mock base path for real filesystem tests
        std::filesystem::create_directories(base_path / p.relative_path());
    }
}

// --- Main Function ---
bool makeNewUserDir(const std::string& username) {
    std::regex username_pattern(R"([a-z_][a-z0-9_-]{0,31})");
    if (!std::regex_match(username, username_pattern)) {
        throw std::invalid_argument("Invalid username format");
    }

    std::filesystem::path path = "/home/" + username;
    bool raised = false;

    try {
        raisePrivileges();
        raised = true;
        mock_fs::create_directory(path);
    }
    catch (const std::filesystem::filesystem_error& e) {
        if (e.code() == std::make_error_code(std::errc::file_exists)) {
            if (raised) {
                try { lowerPrivileges(); } catch (...) {}
            }
            throw;
        }
        throw std::runtime_error("Failed to create directory");
    }
    catch (...) {
        throw std::runtime_error("Unexpected error");
    }

    if (raised) {
        try {
            lowerPrivileges();
        } catch (...) {}
    }

    return true;
}

// --- Test Helpers ---
void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(int actual, int expected, const std::string& message) {
    if (actual != expected) {
        std::cerr << "FAIL: " << message << " (expected " << expected << ", got " << actual << ")" << std::endl;
        std::exit(1);
    }
}

void expect_raises(const std::function<void()>& func, const std::string& exc_type) {
    try {
        func();
        fail("Expected exception: " + exc_type + " but none was thrown");
    } catch (const std::exception&) {
        return;
    }
}

// --- Test Cases ---
void test_normal_creation() {
    MockState::reset();
    bool result = makeNewUserDir("alice");
    expect_true(result, "makeNewUserDir('alice') should return true");
    expect_equal(MockState::raise_count, 1, "raisePrivileges should be called once");
    expect_equal(MockState::lower_count, 1, "lowerPrivileges should be called once");
    expect_equal(MockState::mkdir_count, 1, "mkdir should be called once");
}

void test_directory_exists() {
    MockState::reset();
    MockState::mkdir_should_throw_exists = true;
    expect_raises([]() { makeNewUserDir("bob"); }, "filesystem_error");
    expect_equal(MockState::raise_count, 1, "raisePrivileges should be called once");
    expect_equal(MockState::lower_count, 1, "lowerPrivileges should be called once in finally block");
}

void test_invalid_username_path_traversal() {
    MockState::reset();
    expect_raises([]() { makeNewUserDir("../root"); }, "invalid_argument");
    expect_equal(MockState::raise_count, 0, "raisePrivileges should not be called");
    expect_equal(MockState::lower_count, 0, "lowerPrivileges should not be called");
}

void test_invalid_username_numeric() {
    MockState::reset();
    expect_raises([]() { makeNewUserDir("123"); }, "invalid_argument");
    expect_equal(MockState::raise_count, 0, "raisePrivileges should not be called");
}

void test_invalid_username_uppercase() {
    MockState::reset();
    expect_raises([]() { makeNewUserDir("Alice"); }, "invalid_argument");
}

void test_invalid_username_too_long() {
    MockState::reset();
    expect_raises([]() { makeNewUserDir("a_very_long_username_that_exceeds_thirty_two_chars"); }, "invalid_argument");
}

void test_valid_username_underscore_start() {
    MockState::reset();
    bool result = makeNewUserDir("_valid");
    expect_true(result, "makeNewUserDir('_valid') should return true");
    expect_equal(MockState::raise_count, 1, "raisePrivileges should be called once");
    expect_equal(MockState::lower_count, 1, "lowerPrivileges should be called once");
}

void test_raise_privileges_fails() {
    MockState::reset();
    MockState::raise_should_throw = true;
    expect_raises([]() { makeNewUserDir("charlie"); }, "runtime_error");
    expect_equal(MockState::raise_count, 1, "raisePrivileges should be called once");
    expect_equal(MockState::lower_count, 0, "lowerPrivileges should not be called because raised is false");
}

void test_lower_privileges_throws() {
    MockState::reset();
    MockState::lower_should_throw = true;
    bool result = makeNewUserDir("dave");
    expect_true(result, "makeNewUserDir('dave') should return true even if lowerPrivileges throws");
    expect_equal(MockState::raise_count, 1, "raisePrivileges should be called once");
    expect_equal(MockState::lower_count, 1, "lowerPrivileges should be called once");
}

void test_real_directory_creation() {
    MockState::reset();
    mock_fs::base_path = std::filesystem::current_path() / "Test" / "CWE-250_mitre_1";
    std::filesystem::create_directories(mock_fs::base_path);

    bool result = makeNewUserDir("realuser");
    expect_true(result, "makeNewUserDir('realuser') should return true");
    expect_equal(MockState::raise_count, 1, "raisePrivileges should be called once");
    expect_equal(MockState::lower_count, 1, "lowerPrivileges should be called once");

    std::filesystem::path created_dir = mock_fs::base_path / "home" / "realuser";
    expect_true(std::filesystem::exists(created_dir), "Directory should exist on filesystem");

    std::filesystem::remove_all(mock_fs::base_path);
}

int main() {
    test_normal_creation();
    test_directory_exists();
    test_invalid_username_path_traversal();
    test_invalid_username_numeric();
    test_invalid_username_uppercase();
    test_invalid_username_too_long();
    test_valid_username_underscore_start();
    test_raise_privileges_fails();
    test_lower_privileges_throws();
    test_real_directory_creation();

    std::cout << "All tests passed!" << std::endl;
    return 0;
}