#include <string>
#include <regex>
#include <filesystem>
#include <stdexcept>
#include <system_error>
#include <sys/stat.h>
#include <iostream>
#include <vector>
#include <functional>

namespace fs = std::filesystem;

std::string create_notification_pipe(const std::string& pipe_name) {
    std::regex name_regex(R"([A-Za-z0-9_-]+\.fifo)");
    if (!std::regex_match(pipe_name, name_regex)) {
        throw std::invalid_argument("invalid pipe_name");
    }

    fs::path directory = "Test/CWE-276_01";
    std::error_code ec;

    fs::create_directories(directory, ec);
    if (ec) {
        throw std::runtime_error("Failed to create directory");
    }

    fs::permissions(directory, fs::perms::owner_all, fs::perm_options::replace, ec);
    // Ignore errors on chmod as per the Python reference

    fs::path path = directory / pipe_name;

    if (fs::exists(path, ec)) {
        if (!ec) {
            if (!fs::is_fifo(path)) {
                throw std::runtime_error("path exists and is not a FIFO");
            }
            fs::remove(path, ec);
            if (ec) {
                throw std::runtime_error("Failed to remove existing FIFO");
            }
        }
    }

    if (mkfifo(path.c_str(), 0600) != 0) {
        throw std::runtime_error("Failed to create FIFO");
    }

    // Enforce restrictive permissions explicitly, removing any group/other bits
    fs::permissions(path, fs::perms::owner_read | fs::perms::owner_write, fs::perm_options::replace, ec);
    if (ec) {
        throw std::runtime_error("Failed to set FIFO permissions");
    }

    return "Pipe created.";
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
        fail(message + " (expected '" + expected + "', got '" + actual + "')");
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (...) {
        // Expected exception caught
    }
}

// --- Main Test Entry Point ---

int main() {
    fs::path directory = "Test/CWE-276_01";
    fs::create_directories(directory);

    fs::path path1 = directory / "alerts.fifo";
    fs::path path2 = directory / "a_b-1.fifo";

    // Cleanup any previous test artifacts
    fs::remove(path1);
    fs::remove(path2);

    try {
        // Test 1: Valid pipe "alerts.fifo"
        std::string result1 = create_notification_pipe("alerts.fifo");
        expect_equal(result1, "Pipe created.", "Test 1 result");

        struct stat st1;
        expect_true(stat(path1.c_str(), &st1) == 0, "Test 1 stat");
        expect_true(S_ISFIFO(st1.st_mode), "Test 1 is FIFO");
        expect_true((st1.st_mode & 0777) == 0600, "Test 1 permissions");

        // Test 2: Valid pipe "a_b-1.fifo"
        std::string result2 = create_notification_pipe("a_b-1.fifo");
        expect_equal(result2, "Pipe created.", "Test 2 result");

        struct stat st2;
        expect_true(stat(path2.c_str(), &st2) == 0, "Test 2 stat");
        expect_true(S_ISFIFO(st2.st_mode), "Test 2 is FIFO");
        expect_true((st2.st_mode & 0777) == 0600, "Test 2 permissions");

        // Test 3: Invalid names (should throw std::invalid_argument)
        assert_raises([]() { create_notification_pipe("../evil.fifo"); }, "Test 3a path traversal");
        assert_raises([]() { create_notification_pipe("noext"); }, "Test 3b no extension");
        assert_raises([]() { create_notification_pipe("has space.fifo"); }, "Test 3c space in name");
        assert_raises([]() { create_notification_pipe("/abs.fifo"); }, "Test 3d absolute path");

        // Test 4: Invalid types (C++ overloads enforce std::string, so passing non-strings won't compile.
        // We test that the regex validation correctly rejects invalid string content.)
        assert_raises([]() { create_notification_pipe(""); }, "Test 4a empty string");
        assert_raises([]() { create_notification_pipe(".fifo"); }, "Test 4b only extension");

    } catch (...) {
        fail("Unexpected exception thrown during test execution");
    }

    // Cleanup
    fs::remove(path1);
    fs::remove(path2);

    return 0;
}