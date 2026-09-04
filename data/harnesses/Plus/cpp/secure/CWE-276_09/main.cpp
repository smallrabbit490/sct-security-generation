#include <string>
#include <fstream>
#include <filesystem>
#include <regex>
#include <stdexcept>
#include <iostream>
#include <functional>

namespace fs = std::filesystem;

std::string export_user_report(const std::string& user_id, const std::string& report_text) {
    std::string uid = user_id;
    // Trim leading and trailing whitespace
    size_t start = uid.find_first_not_of(" \t\n\r\f\v");
    if (start == std::string::npos) {
        uid.clear();
    } else {
        size_t end = uid.find_last_not_of(" \t\n\r\f\v");
        uid = uid.substr(start, end - start + 1);
    }

    if (uid.empty()) {
        throw std::invalid_argument("empty user_id");
    }

    // Allow a simple identifier; avoids path separators and odd characters
    std::regex uid_regex("^[A-Za-z0-9_-]+$");
    if (!std::regex_match(uid, uid_regex)) {
        throw std::invalid_argument("invalid user_id");
    }

    fs::path base_dir = "Test/CWE-276_09/reports";
    fs::path user_dir = base_dir / uid;

    std::error_code ec;
    fs::create_directories(user_dir, ec);
    if (ec) {
        throw std::runtime_error("Failed to create directory");
    }

    // Set directory permissions to owner-only (rwx------)
    fs::permissions(user_dir,
                    fs::perms::owner_read | fs::perms::owner_write | fs::perms::owner_exec,
                    fs::perm_options::replace, ec);
    if (ec) {
        // Ignore failure to set permissions, as in the Python try/except pass
    }

    fs::path path = user_dir / "report.txt";
    std::ofstream out_file(path, std::ios::out | std::ios::trunc);
    if (!out_file) {
        throw std::runtime_error("Failed to open report file");
    }

    out_file << report_text;
    out_file.close();
    if (out_file.fail()) {
        throw std::runtime_error("Failed to write report file");
    }

    // Set file permissions to owner-only (rw-------)
    fs::permissions(path,
                    fs::perms::owner_read | fs::perms::owner_write,
                    fs::perm_options::replace, ec);
    if (ec) {
        throw std::runtime_error("Failed to set file permissions");
    }

    return "Report exported.";
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
    } catch (const std::exception&) {
        // Expected exception caught
    }
}

int main() {
    fs::path base = "Test/CWE-276_09/reports";

    // Cleanup before tests
    std::error_code ec;
    fs::remove_all("Test", ec);

    try {
        // valid user report
        std::string res1 = export_user_report("user123", "hello");
        expect_equal(res1, "Report exported.", "Valid user report return value");
        
        fs::path user_dir1 = base / "user123";
        fs::path path1 = user_dir1 / "report.txt";
        expect_true(fs::exists(path1), "Report file exists for user123");
        
        std::ifstream ifs1(path1);
        std::string content1((std::istreambuf_iterator<char>(ifs1)), std::istreambuf_iterator<char>());
        expect_equal(content1, "hello", "Report content for user123");

        // another valid user_id
        std::string res2 = export_user_report("u_1-2", "x");
        expect_equal(res2, "Report exported.", "Valid user_id u_1-2 return value");
        
        fs::path user_dir2 = base / "u_1-2";
        fs::path path2 = user_dir2 / "report.txt";
        expect_true(fs::exists(path2), "Report file exists for u_1-2");

        // invalid user_id (path separator)
        assert_raises([]() { export_user_report("bad/user", "x"); }, "Invalid user_id (path separator)");

        // invalid user_id (traversal-like)
        assert_raises([]() { export_user_report("../evil", "x"); }, "Invalid user_id (traversal-like)");

        // empty user_id
        assert_raises([]() { export_user_report("   ", "x"); }, "Empty user_id");

        // invalid types (C++ is statically typed, so passing non-strings is a compile-time error.
        // We test that the function correctly enforces string constraints at runtime).
        assert_raises([]() { export_user_report("", "x"); }, "Empty string user_id");
        assert_raises([]() { export_user_report("bad user", "x"); }, "Invalid user_id (space)");
        assert_raises([]() { export_user_report("bad.user", "x"); }, "Invalid user_id (dot)");

    } catch (const std::exception& e) {
        fail(std::string("Unexpected exception: ") + e.what());
    }

    // Cleanup after tests
    fs::remove_all("Test", ec);

    std::cout << "All tests passed!" << std::endl;
    return 0;
}