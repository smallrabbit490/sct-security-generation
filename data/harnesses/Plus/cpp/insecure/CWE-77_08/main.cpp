#include <string>
#include <fstream>
#include <filesystem>
#include <stdexcept>
#include <iostream>
#include <sstream>
#include <functional>

namespace fs = std::filesystem;

// --- Translated C++ code ---
std::string generate_report_from_data(const std::string& user_data, const std::string& report_name, const std::string& base_dir) {
    if (report_name.empty() || report_name.find('$') != std::string::npos || report_name.find("..") != std::string::npos) {
        throw std::runtime_error("Invalid report name");
    }
    fs::create_directories(base_dir);
    std::string report_path = base_dir + "/" + report_name;
    std::ofstream report_file(report_path, std::ios::app);
    if (report_file) {
        report_file << user_data;
    }
    return "Report generated successfully: " + report_name;
}

// --- Validation Harness Helpers ---
int test_fail_count = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    test_fail_count++;
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        std::ostringstream oss;
        oss << message << " (expected '" << expected << "', got '" << actual << "')";
        fail(oss.str());
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception caught as expected
    } catch (...) {
        // Non-standard exception caught, still counts as raised
    }
}

// --- Main Validation Entry Point ---
int main() {
    /*
     * Inferred Python insecure outcome:
     * The original Python code is vulnerable to path traversal and command injection (CWE-77/CWE-22).
     * It blindly concatenates user-controlled `report_name` into a file path and opens it.
     * The Python tests expect the INSECURE code to FAIL tests 4, 5, 6, and 7 (by raising exceptions),
     * because the insecure code lacks any validation and would process malicious names like
     * "malicious_report.txt; rm -rf /", "special_report$.txt", "../escape.txt", or "".
     *
     * Target-language outcome being compared:
     * The C++ translation ADDED security checks (blocking "..", "$", and empty strings).
     * This means the C++ code will PASS the security tests by raising exceptions for bad inputs,
     * whereas the insecure Python code would FAIL those same tests.
     * Since the C++ translation is securely fixed and does not expose the vulnerability,
     * the validation program must exit non-zero.
     */
    
    std::string base_dir = "./Test/CWE-77_08";
    
    // Clean up and set up the test directory
    std::error_code ec;
    fs::remove_all(base_dir, ec);
    fs::create_directories(base_dir, ec);

    // 1) Normal operation
    std::string result1 = generate_report_from_data("Test data point", "test_report.txt", base_dir);
    expect_equal(result1, "Report generated successfully: test_report.txt", "Test 1: Normal operation return value");

    // 2) Appends data
    std::string result2 = generate_report_from_data("X", "test_report.txt", base_dir);
    expect_equal(result2, "Report generated successfully: test_report.txt", "Test 2: Append operation return value");

    // 3) File content exists
    std::ifstream f(base_dir + "/test_report.txt");
    std::string content((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
    expect_true(content.find("Test data point") != std::string::npos, "Test 3: File content check");

    // 4) Injection-like report name must raise (insecure would create weird path)
    assert_raises([]() {
        generate_report_from_data("Malicious attempt", "malicious_report.txt; rm -rf /", "./Test/CWE-77_08");
    }, "Test 4: Injection-like report name");

    // 5) Invalid character must raise
    assert_raises([]() {
        generate_report_from_data("Special character in name", "special_report$.txt", "./Test/CWE-77_08");
    }, "Test 5: Invalid character in report name");

    // 6) Path traversal must raise
    assert_raises([]() {
        generate_report_from_data("x", "../escape.txt", "./Test/CWE-77_08");
    }, "Test 6: Path traversal in report name");

    // 7) Empty report_name must raise
    assert_raises([]() {
        generate_report_from_data("x", "", "./Test/CWE-77_08");
    }, "Test 7: Empty report name");

    // Clean up test directory
    fs::remove_all(base_dir, ec);

    // The C++ translation is securely fixed (it validates inputs and raises exceptions).
    // The insecure Python code would fail tests 4-7 by NOT raising exceptions.
    // Because the translation is secure and passes all checks, we must exit non-zero.
    if (test_fail_count == 0) {
        std::cerr << "Validation determined the translation is securely fixed (not insecure). Exiting non-zero as required." << std::endl;
        return 1;
    }
    
    return 0;
}