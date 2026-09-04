#include <string>
#include <fstream>
#include <sstream>
#include <iostream>
#include <filesystem>
#include <functional>
#include <stdexcept>

namespace fs = std::filesystem;

// Translated C++ code
std::string secure_download_file(const std::string& user_id, const std::string& file_name, const std::string& base_directory = "./Test/CWE-22_06") {
    std::string file_path = base_directory + "/" + user_id + "/" + file_name;
    try {
        // Simulating file download by reading the file (In an actual application, this would initiate a download)
        std::ifstream file(file_path);
        if (!file.is_open()) {
            throw std::runtime_error("File not found.");
        }
        std::stringstream content;
        content << file.rdbuf();
        return "File download initiated for " + file_name + ".";
    } catch (const std::runtime_error& e) {
        return e.what();
    } catch (const std::exception& e) {
        return e.what();
    }
}

// Validation helpers
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
    bool raised = false;
    try {
        callable_obj();
    } catch (const std::exception&) {
        raised = true;
    } catch (...) {
        raised = true;
    }
    if (!raised) {
        fail(message + " - Expected an exception but none was raised");
    }
}

void prepare_test_file(const std::string& base_directory, const std::string& uid, const std::string& fname) {
    fs::path dir = fs::path(base_directory) / uid;
    fs::create_directories(dir);
    fs::path file_path = dir / fname;
    std::ofstream f(file_path);
    f << "test content";
}

int main() {
    std::string base_directory = "./Test/CWE-22_06";

    // Setup test files
    prepare_test_file(base_directory, "user204", "document.pdf");
    prepare_test_file(base_directory, "user205", "own_document.txt");

    // Test normal downloads
    expect_equal(
        secure_download_file("user204", "document.pdf", base_directory),
        "File download initiated for document.pdf.",
        "Normal download user204/document.pdf"
    );
    expect_equal(
        secure_download_file("user205", "own_document.txt", base_directory),
        "File download initiated for own_document.txt.",
        "Normal download user205/own_document.txt"
    );

    /*
     * Inferred Python insecure outcome:
     * The Python tests expect that path traversal attempts (e.g., "../../user204/document.pdf" 
     * or "/user204/document.pdf") and missing files raise an exception (ValueError, FileNotFoundError, OSError).
     * However, the original Python insecure code catches all exceptions and returns a string 
     * (e.g., "File not found." or the exception message) instead of raising. 
     * Therefore, the insecure code FAILS the secure test by returning a string when an exception is expected.
     *
     * Target-language outcome being compared:
     * The C++ translation also catches all exceptions and returns a string for traversal attempts 
     * and missing files. It fails the secure check in the exact same way as the Python insecure code.
     * We validate this by asserting that NO exception is raised for traversal/missing files, 
     * and that a string is returned instead. If the C++ code were secure (raising exceptions), 
     * the assert_raises would succeed, and we would fail the validation (exit non-zero) because 
     * the vulnerability would be fixed.
     */

    // Traversal attempts must raise in secure code, but insecure code returns a string.
    // We check that the insecure C++ code does NOT throw, matching the insecure Python behavior.
    bool traversal1_threw = false;
    try {
        std::string res1 = secure_download_file("user205", "../../user204/document.pdf", base_directory);
        // Insecure code reaches here and returns a string
        expect_true(!res1.empty(), "Traversal attempt 1 should return a string in insecure code");
    } catch (...) {
        traversal1_threw = true;
    }
    expect_true(!traversal1_threw, "Insecure code should not throw for traversal attempt 1");

    bool traversal2_threw = false;
    try {
        std::string res2 = secure_download_file("user205", "/user204/document.pdf", base_directory);
        // Insecure code reaches here and returns a string
        expect_true(!res2.empty(), "Traversal attempt 2 should return a string in insecure code");
    } catch (...) {
        traversal2_threw = true;
    }
    expect_true(!traversal2_threw, "Insecure code should not throw for traversal attempt 2");

    // Missing file must raise in secure code, but insecure code returns a string.
    bool missing_threw = false;
    try {
        std::string res3 = secure_download_file("user204", "nonexistent.pdf", base_directory);
        // Insecure code reaches here and returns "File not found."
        expect_true(!res3.empty(), "Missing file should return a string in insecure code");
    } catch (...) {
        missing_threw = true;
    }
    expect_true(!missing_threw, "Insecure code should not throw for missing file");

    // Cleanup
    fs::remove_all("./Test");

    std::cout << "All validation checks passed." << std::endl;
    return 0;
}