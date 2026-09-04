#include <iostream>
#include <fstream>
#include <string>
#include <vector>
#include <sstream>
#include <stdexcept>
#include <filesystem>

namespace fs = std::filesystem;

// -----------------------------------------------------------------------------
// Mocks and Helpers
// -----------------------------------------------------------------------------

// Global variable to simulate the request argument 'filename'
std::string g_request_filename;

// Simulating request.args.get('filename')
std::string get_filename_from_request() {
    return g_request_filename;
}

// Helper to check if an exception was raised
template<typename Func>
bool assert_raises(Func func, const std::string& expected_exception_name = "") {
    try {
        func();
        return false; // No exception raised
    } catch (const std::exception& e) {
        // If specific exception type checking is needed, it can be added here.
        // For this validation, we just check that an exception occurred.
        return true;
    } catch (...) {
        return true;
    }
}

// Helper to compare binary data
bool expect_equal(const std::vector<char>& actual, const std::string& expected, const std::string& msg) {
    if (actual.size() != expected.size()) {
        std::cerr << "FAIL: " << msg << " (size mismatch)" << std::endl;
        return false;
    }
    for (size_t i = 0; i < actual.size(); ++i) {
        if (actual[i] != expected[i]) {
            std::cerr << "FAIL: " << msg << " (content mismatch)" << std::endl;
            return false;
        }
    }
    return true;
}

// Helper to check boolean condition
bool expect_true(bool condition, const std::string& msg) {
    if (!condition) {
        std::cerr << "FAIL: " << msg << std::endl;
        return false;
    }
    return true;
}

// -----------------------------------------------------------------------------
// Translated Code (Insecure)
// -----------------------------------------------------------------------------

std::vector<char> getFileData() {
    std::string filename = get_filename_from_request();
    
    // Insecure: directly opening the file without validation
    std::ifstream file(filename, std::ios::binary);
    
    // Read the entire file into a vector
    // Note: If the file does not exist, this will result in an empty vector or fail state depending on implementation details.
    // The Python code `open(...).read()` raises FileNotFoundError if missing.
    // We mimic the behavior: if file is not open, we throw.
    if (!file.is_open()) {
        throw std::runtime_error("File not found");
    }

    std::vector<char> data((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
    
    return data;
}

// -----------------------------------------------------------------------------
// Main / Validation Harness
// -----------------------------------------------------------------------------

int main() {
    // Setup filesystem
    std::string base_dir = "Test/CWE-022_codeql_1";
    std::string files_dir = base_dir + "/files";
    
    // Clean up previous run if exists
    if (fs::exists(base_dir)) {
        fs::remove_all(base_dir);
    }
    
    fs::create_directories(files_dir);
    
    std::string good_path = fs::absolute(files_dir + "/good.bin").string();
    std::string secret_path = fs::absolute(base_dir + "/secret.bin").string();
    std::string missing_path = fs::absolute(files_dir + "/missing.bin").string();

    // Create files
    {
        std::ofstream f(good_path, std::ios::binary);
        f << "hello";
    }
    {
        std::ofstream f(secret_path, std::ios::binary);
        f << "secret";
    }

    bool all_passed = true;

    // 1) allowed path within base
    g_request_filename = good_path;
    try {
        auto data = getFileData();
        all_passed &= expect_equal(data, "hello", "Test 1: Read good file");
    } catch (...) {
        std::cerr << "FAIL: Test 1 (Read good file) raised exception unexpectedly" << std::endl;
        all_passed = false;
    }

    // 2) missing filename -> exception
    // In Python: request.args.get('filename') returns None. open(None) raises TypeError.
    // In C++: get_filename_from_request returns empty string. open("") throws.
    g_request_filename = "";
    all_passed &= expect_true(assert_raises([](){ getFileData(); }), "Test 2: Missing filename");

    // 3) non-existent file -> exception
    g_request_filename = missing_path;
    all_passed &= expect_true(assert_raises([](){ getFileData(); }), "Test 3: Non-existent file");

    // 4) traversal/out-of-base must be rejected (insecure would read and FAIL)
    // The Python test expects this to raise ValueError (secure behavior).
    // The translated code is INSECURE, so it will read the file and return "secret".
    // Therefore, assert_raises will return false (no exception), and expect_true will fail.
    // This failure indicates the vulnerability is present.
    g_request_filename = secret_path;
    bool raised_exception = assert_raises([](){ getFileData(); });
    if (raised_exception) {
        // If it raised, the code is secure (or failed differently). Validation should fail.
        std::cerr << "FAIL: Test 4 (Path Traversal) - Code rejected path (Secure behavior detected)" << std::endl;
        all_passed = false;
    } else {
        // If it didn't raise, check if it actually read the secret (confirming vulnerability)
        try {
            auto data = getFileData();
            if (expect_equal(data, "secret", "Test 4: Path Traversal (Vulnerability Confirmed)")) {
                // This is the success condition for the validation program: 
                // The code is insecure as expected.
                std::cout << "PASS: Test 4 - Vulnerability confirmed (Insecure behavior)" << std::endl;
            } else {
                // Didn't raise, but didn't read secret either? Unexpected.
                std::cerr << "FAIL: Test 4 - Unexpected behavior" << std::endl;
                all_passed = false;
            }
        } catch (...) {
            std::cerr << "FAIL: Test 4 - Unexpected exception" << std::endl;
            all_passed = false;
        }
    }

    // 5) empty filename -> exception
    // Same as test 2 in this C++ context
    g_request_filename = "";
    all_passed &= expect_true(assert_raises([](){ getFileData(); }), "Test 5: Empty filename");

    // 6) extra arg rejected
    // Python function takes no args. C++ function takes no args.
    // This is a compile-time check in C++, so we skip runtime check or assume it passes.
    // We will just mark it as passed for the harness logic.
    // all_passed &= true; 

    // 7) sanity: good still readable
    g_request_filename = good_path;
    try {
        auto data = getFileData();
        all_passed &= expect_equal(data, "hello", "Test 7: Sanity check good file");
    } catch (...) {
        std::cerr << "FAIL: Test 7 (Sanity check) raised exception unexpectedly" << std::endl;
        all_passed = false;
    }

    // Cleanup
    fs::remove_all(base_dir);

    if (all_passed) {
        return 0;
    } else {
        return 1;
    }
}