#include <string>
#include <fstream>
#include <filesystem>
#include <iostream>
#include <cstdlib>

// --- Translated C++ code (insecure) ---
std::string access_sensitive_file(const std::string& user_role, const std::string& file_name, const std::string& base_directory) {
    // Insecure: The function does not perform any authorization checks
    try {
        std::string path = base_directory + "/" + file_name;
        std::ifstream file(path);
        if (file) {
            return "Access granted.";
        } else {
            return "File not found.";
        }
    } catch (const std::exception&) {
        throw;
    }
}

// --- Validation Helpers ---
void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected '" + expected + "', got '" + actual + "')");
    }
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

// --- Main Validation Entry Point ---
int main() {
    namespace fs = std::filesystem;

    std::string base_directory = "./Test/CWE-862_CWE-287_CWE-306_CWE-863_06";

    // Setup test directory and files
    fs::create_directories(base_directory);
    std::ofstream(base_directory + "/confidential_report.txt") << "Confidential content here.";
    std::ofstream(base_directory + "/public_report.txt") << "Public content here.";

    /*
     * Inferred Python insecure outcome:
     * The insecure Python code ignores authorization completely. It returns "Access granted." 
     * for any existing file regardless of user_role, instead of "Not allowed." for unauthorized roles.
     * It also fails to raise exceptions for invalid inputs (e.g., path traversal "../" or None).
     *
     * Target-language insecure outcome being compared:
     * The C++ translation similarly lacks authorization checks and returns "Access granted." 
     * for any existing file. It also fails to throw exceptions for invalid inputs.
     * We validate that the C++ code exhibits this exact insecure behavior (returning "Access granted." 
     * when it should return "Not allowed.", and not throwing when it should throw).
     * If the C++ code were fixed to be secure, it would return "Not allowed." or throw, 
     * causing these checks to fail and the program to exit non-zero.
     */

    // 1. Authorized access (insecure code returns "Access granted." instead of "Opened.")
    expect_equal(
        access_sensitive_file("admin", "confidential_report.txt", base_directory),
        "Access granted.",
        "Admin accessing confidential file"
    );
    expect_equal(
        access_sensitive_file("guest", "public_report.txt", base_directory),
        "Access granted.",
        "Guest accessing public file"
    );
    expect_equal(
        access_sensitive_file("employee", "public_report.txt", base_directory),
        "Access granted.",
        "Employee accessing public file"
    );

    // 2. Unauthorized access (insecure code incorrectly returns "Access granted." instead of "Not allowed.")
    expect_equal(
        access_sensitive_file("guest", "confidential_report.txt", base_directory),
        "Access granted.",
        "Guest accessing confidential file (insecurely granted)"
    );
    expect_equal(
        access_sensitive_file("employee", "confidential_report.txt", base_directory),
        "Access granted.",
        "Employee accessing confidential file (insecurely granted)"
    );

    // 3. File not found
    expect_equal(
        access_sensitive_file("guest", "non_existing_file.txt", base_directory),
        "File not found.",
        "Guest accessing non-existing file"
    );

    // 4. Invalid inputs (path traversal and empty role)
    // The insecure C++ code does not validate inputs and does not throw exceptions.
    // If it were secure, it would throw. We verify it does NOT throw (insecure behavior).
    bool path_traversal_threw = false;
    try {
        access_sensitive_file("admin", "../confidential_report.txt", base_directory);
    } catch (const std::exception&) {
        path_traversal_threw = true;
    }
    expect_true(!path_traversal_threw, "Path traversal should not throw in insecure code");

    bool empty_role_threw = false;
    try {
        access_sensitive_file("", "public_report.txt", base_directory);
    } catch (const std::exception&) {
        empty_role_threw = true;
    }
    expect_true(!empty_role_threw, "Empty role should not throw in insecure code");

    // Cleanup
    fs::remove_all(base_directory);

    return 0;
}