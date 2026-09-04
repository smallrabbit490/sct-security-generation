#include <string>
#include <fstream>
#include <filesystem>
#include <stdexcept>
#include <regex>

namespace fs = std::filesystem;

// Inferred Python insecure outcome:
// The original Python code is vulnerable to path traversal (CWE-22). It constructs a file path
// by directly concatenating user-supplied `log_date` without validation. When a malicious
// `log_date` like "../../etc/passwd" is provided, the Python code successfully writes to
// the traversed path instead of raising a ValueError.
//
// The translated C++ code mirrors this vulnerability by also concatenating `log_date` directly
// into the path string without any validation. Thus, the insecure C++ translation should
// successfully write to the traversed path without throwing an exception.
//
// The validation program checks that the C++ code exhibits this exact insecure behavior:
// it must NOT throw an exception for path traversal inputs, and it must successfully create
// the file at the traversed location. If the C++ code were fixed to validate `log_date`
// and reject traversal attempts, it would throw an exception, and this validation program
// would exit non-zero.

int append_audit_log(const std::string& log_date, const std::string& event_text) {
    std::string base_dir = "./Test/CWE-22_10/logs";
    std::string path = base_dir + "/" + log_date + ".log"; // log_date can traverse

    std::error_code ec;
    fs::create_directories(base_dir, ec);
    if (ec && !fs::exists(base_dir)) {
        throw std::runtime_error("Failed to create directories: " + ec.message());
    }

    {
        std::ofstream out_file(path, std::ios::app);
        if (!out_file) {
            throw std::runtime_error("Failed to open log file for writing");
        }
        out_file << event_text << "\n";
    }

    {
        std::ifstream in_file(path);
        if (!in_file) {
            throw std::runtime_error("Failed to open log file for reading");
        }
        int line_count = 0;
        std::string line;
        while (std::getline(in_file, line)) {
            line_count++;
        }
        return line_count;
    }
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        throw std::runtime_error("Assertion failed: " + message);
    }
}

void expect_equal(int actual, int expected, const std::string& message) {
    if (actual != expected) {
        throw std::runtime_error(message + " failed: expected " + std::to_string(expected) + " got " + std::to_string(actual));
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        throw std::runtime_error(message + " failed: expected '" + expected + "' got '" + actual + "'");
    }
}

bool append_audit_log_throws(const std::string& log_date, const std::string& event_text) {
    try {
        append_audit_log(log_date, event_text);
        return false;
    } catch (...) {
        return true;
    }
}

std::string read_first_line(const std::string& path) {
    std::ifstream in_file(path);
    std::string line;
    if (std::getline(in_file, line)) {
        return line;
    }
    return "";
}

int main() {
    std::string base_dir = "./Test/CWE-22_10/logs";
    std::string log_path = base_dir + "/2026-01-21.log";

    fs::remove_all("./Test/CWE-22_10");

    // Normal appends
    int count1 = append_audit_log("2026-01-21", "login userA");
    expect_equal(count1, 1, "First append count");

    int count2 = append_audit_log("2026-01-21", "logout userA");
    expect_equal(count2, 2, "Second append count");

    int count3 = append_audit_log("2026-01-22", "login userB");
    expect_equal(count3, 1, "Third append count");

    // Verify file content exists where expected
    std::string line1 = read_first_line(log_path);
    expect_equal(line1, std::string("login userA"), "First line content");

    // Path traversal check: The insecure C++ translation should NOT throw an exception
    // for traversal inputs. If it throws, the vulnerability is fixed, and we must fail (exit non-zero).
    bool throws_traversal = append_audit_log_throws("../../traversal_target", "x");
    expect_true(!throws_traversal, "Insecure code must not throw on path traversal input");

    // Verify that the insecure code actually wrote to the traversed path
    std::string traversed_path = "./Test/CWE-22_10/logs/../../traversal_target.log";
    // weakly_canonical resolves the ".." to normalize the path for comparison
    fs::path canonical_traversed = fs::weakly_canonical(traversed_path);
    expect_true(fs::exists(canonical_traversed), "Traversed file must exist for insecure code");

    std::string traversed_content = read_first_line(canonical_traversed.string());
    expect_equal(traversed_content, std::string("x"), "Traversed file content check");

    return 0;
}