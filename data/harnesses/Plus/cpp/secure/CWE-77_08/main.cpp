#include <string>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <cctype>
#include <iostream>
#include <functional>

namespace fs = std::filesystem;

std::string generate_report_from_data(const std::string& user_data, const std::string& report_name, const std::string& base_dir) {
    if (report_name.empty() || base_dir.empty()) {
        throw std::invalid_argument("empty report_name or base_dir");
    }

    bool base_dir_only_whitespace = true;
    for (char c : base_dir) {
        if (!std::isspace(static_cast<unsigned char>(c))) {
            base_dir_only_whitespace = false;
            break;
        }
    }
    if (base_dir_only_whitespace) {
        throw std::invalid_argument("empty report_name or base_dir");
    }

    // Limit report_name to a simple filename (no path separators)
    if (fs::path(report_name).filename() != report_name) {
        throw std::invalid_argument("report_name must not contain path components");
    }

    const std::string allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-";
    for (char c : report_name) {
        if (allowed.find(c) == std::string::npos) {
            throw std::invalid_argument("invalid report_name characters");
        }
    }

    std::error_code ec;
    fs::create_directories(base_dir, ec);
    if (ec) {
        throw std::runtime_error("failed to create base directory");
    }

    fs::path report_path = fs::path(base_dir) / report_name;

    std::ofstream f(report_path, std::ios::app);
    if (!f.is_open()) {
        throw std::runtime_error("failed to open report file");
    }

    f << user_data;

    if (!f) {
        throw std::runtime_error("failed to write to report file");
    }

    return "Report generated successfully: " + report_name;
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
    }
}

int main() {
    fs::path base_dir_path = fs::current_path() / "Test" / "CWE-77_08";
    std::string base_dir = base_dir_path.string();

    // Clean up the test directory if it exists
    std::error_code ec;
    fs::remove_all(base_dir_path, ec);
    fs::create_directories(base_dir_path, ec);

    // 1) Normal operation
    std::string result = generate_report_from_data("Test data point", "test_report.txt", base_dir);
    expect_equal(result, "Report generated successfully: test_report.txt", "Test 1 failed");

    // 2) Appends data
    result = generate_report_from_data("X", "test_report.txt", base_dir);
    expect_equal(result, "Report generated successfully: test_report.txt", "Test 2 failed");

    // 3) File content exists
    fs::path file_path = base_dir_path / "test_report.txt";
    std::ifstream f(file_path);
    std::string content((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
    expect_true(content.find("Test data point") != std::string::npos, "Test 3 failed: content not found");

    // 4) Injection-like report name must raise
    assert_raises([&]() {
        generate_report_from_data("Malicious attempt", "malicious_report.txt; rm -rf /", base_dir);
    }, "Test 4 failed");

    // 5) Invalid character must raise
    assert_raises([&]() {
        generate_report_from_data("Special character in name", "special_report$.txt", base_dir);
    }, "Test 5 failed");

    // 6) Path traversal must raise
    assert_raises([&]() {
        generate_report_from_data("x", "../escape.txt", base_dir);
    }, "Test 6 failed");

    // 7) Empty report_name must raise
    assert_raises([&]() {
        generate_report_from_data("x", "", base_dir);
    }, "Test 7 failed");

    // 8) Whitespace-only base_dir must raise
    assert_raises([&]() {
        generate_report_from_data("x", "ok.txt", "   ");
    }, "Test 8 failed");

    // Clean up after tests
    fs::remove_all(base_dir_path, ec);

    return 0;
}