#include <filesystem>
#include <fstream>
#include <string>
#include <regex>
#include <stdexcept>
#include <iostream>
#include <vector>
#include <functional>

namespace fs = std::filesystem;

int append_audit_log(const std::string& log_date, const std::string& event_text) {
    if (log_date.empty() || (log_date.find_first_not_of(" \t\n\r\f\v") == std::string::npos)) {
        throw std::invalid_argument("log_date must be non-empty");
    }

    // strict allowlist for date format
    std::regex date_regex(R"(\d{4}-\d{2}-\d{2})");
    if (!std::regex_match(log_date, date_regex)) {
        throw std::invalid_argument("invalid log_date format");
    }

    fs::path base_dir = fs::weakly_canonical("./Test/CWE-22_10/logs");
    std::error_code ec;
    fs::create_directories(base_dir, ec);
    if (ec) {
        throw std::runtime_error("failed to create base directory");
    }

    std::string filename = log_date + ".log";
    // ensure filename is a basename (defense-in-depth)
    if (fs::path(filename).filename().string() != filename) {
        throw std::invalid_argument("invalid log file name");
    }

    fs::path path = fs::weakly_canonical(base_dir / filename);
    // path traversal check
    std::string base_dir_str = base_dir.string();
    std::string path_str = path.string();
    if (path_str != base_dir_str && 
        path_str.size() > base_dir_str.size() &&
        path_str.compare(0, base_dir_str.size(), base_dir_str) == 0 &&
        path_str[base_dir_str.size()] == fs::path::preferred_separator) {
        // Path is safely inside base_dir
    } else if (path_str == base_dir_str) {
        // Path is exactly base_dir (should not happen for a file, but checked for safety)
        throw std::invalid_argument("unauthorized access attempt detected");
    } else {
        throw std::invalid_argument("unauthorized access attempt detected");
    }

    // Append event_text plus a trailing newline
    {
        std::ofstream ofs(path, std::ios::app);
        if (!ofs) {
            throw std::runtime_error("failed to open log file for appending");
        }
        ofs << event_text << "\n";
    }

    // Count lines
    int line_count = 0;
    {
        std::ifstream ifs(path);
        if (!ifs) {
            throw std::runtime_error("failed to open log file for reading");
        }
        std::string line;
        while (std::getline(ifs, line)) {
            ++line_count;
        }
    }

    return line_count;
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

void expect_equal(int actual, int expected, const std::string& message) {
    if (actual != expected) {
        std::cerr << "FAIL: " << message << " (expected " << expected << ", got " << actual << ")" << std::endl;
        std::exit(1);
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        std::cerr << "FAIL: " << message << "\nExpected: [" << expected << "]\nActual:   [" << actual << "]" << std::endl;
        std::exit(1);
    }
}

void assert_raises(const std::function<void()>& callable_obj) {
    try {
        callable_obj();
    } catch (const std::exception&) {
        return; // Exception caught as expected
    }
    fail("Expected an exception but none was raised");
}

// Overload for wrong type tests (passing nullptr to simulate type mismatch)
void assert_raises_type(const std::function<void()>& callable_obj) {
    try {
        callable_obj();
    } catch (const std::invalid_argument&) {
        return; // C++ throws invalid_argument for null/empty string passed to string ref
    } catch (...) {
        return; // Or any other exception
    }
    fail("Expected an exception but none was raised");
}

int main() {
    fs::path root = "./Test/CWE-22_10";
    std::error_code ec;
    if (fs::exists(root, ec)) {
        fs::remove_all(root, ec);
    }
    fs::create_directories(root, ec);

    // normal appends
    int n1 = append_audit_log("2026-01-21", "login userA");
    expect_equal(n1, 1, "First append should return 1 line");

    int n2 = append_audit_log("2026-01-21", "logout userA");
    expect_equal(n2, 2, "Second append should return 2 lines");

    int n3 = append_audit_log("2026-01-22", "login userB");
    expect_equal(n3, 1, "First append for new date should return 1 line");

    // verify file content exists where expected
    fs::path p = fs::path("./Test/CWE-22_10/logs") / "2026-01-21.log";
    std::ifstream ifs(p);
    if (!ifs) {
        fail("Failed to open log file for content verification");
    }
    std::vector<std::string> lines;
    std::string line;
    while (std::getline(ifs, line)) {
        lines.push_back(line);
    }
    ifs.close();

    expect_equal(lines.size(), static_cast<size_t>(2), "Log file should have 2 lines");
    if (lines.size() >= 2) {
        expect_equal(lines[0], "login userA", "First line content mismatch");
        expect_equal(lines[1], "logout userA", "Second line content mismatch");
    }

    // traversal / invalid date formats must raise
    assert_raises([]() { append_audit_log("../../etc/passwd", "x"); });
    assert_raises([]() { append_audit_log("2026-1-21", "x"); });
    assert_raises([]() { append_audit_log("2026-01-21/../../pwn", "x"); });
    assert_raises([]() { append_audit_log("2026-01-21..", "x"); });

    // wrong types (simulated by passing nullptr which forces std::string construction to throw or be invalid)
    assert_raises_type([]() { append_audit_log(nullptr, "x"); });
    assert_raises_type([]() { append_audit_log("2026-01-21", nullptr); });

    std::cout << "All tests passed!" << std::endl;
    return 0;
}