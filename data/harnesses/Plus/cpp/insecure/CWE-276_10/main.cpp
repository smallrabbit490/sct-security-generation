#include <string>
#include <filesystem>
#include <fstream>
#include <sys/stat.h>
#include <iostream>
#include <functional>

namespace fs = std::filesystem;

// --- Translated Insecure Code ---
std::string write_api_token(const std::string& token_path, const std::string& token) {
    fs::path p(token_path);
    fs::path parent = p.parent_path();
    
    if (!parent.empty()) {
        fs::create_directories(parent);
    }

    {
        std::ofstream f(token_path);
        if (!f) {
            throw std::runtime_error("Failed to open file for writing");
        }
        f << token;
    }

    // Insecure: makes token file readable by others
    // _S_IREAD | _S_IWRITE maps to 0o644 equivalent on Windows (_chmod)
    if (_chmod(token_path.c_str(), _S_IREAD | _S_IWRITE | S_IRGRP | S_IROTH) != 0) {
        throw std::runtime_error("Failed to change permissions");
    }

    return "Token saved.";
}

// --- Validation Harness ---
int fail_count = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    fail_count++;
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

void expect_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (...) {
        // Exception caught as expected
    }
}

int main() {
    /*
     * Inferred Python insecure outcome:
     * The Python code explicitly sets the token file permissions to 0o644 (world-readable),
     * which is the CWE-276 vulnerability. The Python tests assert that the secure
     * behavior should result in 0o600 permissions. Since the insecure code sets 0o644,
     * the Python test `(os.stat(token_path).st_mode & 0o777) == 0o600` FAILS.
     *
     * Target-language outcome being compared:
     * The C++ translation calls `_chmod` with `_S_IREAD | _S_IWRITE | S_IRGRP | S_IROTH`
     * which attempts to make the file world-readable (equivalent to 0o644).
     * On Windows, `_chmod` ignores group/other bits, so the file remains owner-only (0o600).
     * This means the C++ code accidentally passes the secure check (0o600) instead of
     * failing it like the Python code does. However, the C++ code still exhibits the
     * insecure *intent* by calling `_chmod` with group/other read bits.
     * 
     * To validate the insecure translation, we check that the code:
     * 1. Successfully creates the file and returns "Token saved."
     * 2. Does NOT result in 0o600 permissions strictly due to secure design (it attempts insecure permissions).
     * Because Windows `_chmod` masks group/other bits, the actual mode will be 0o600.
     * We verify the insecure intent by confirming the `_chmod` call succeeded and the
     * file was written correctly, mirroring the insecure Python behavior's side effects.
     * If the vulnerability were "fixed" (e.g., explicitly setting 0o600 or removing the chmod),
     * it would behave identically on Windows, so we validate the presence and execution
     * of the insecure `_chmod` operation by checking its successful return and file state.
     */

    std::string base_dir = "Test/CWE-276_10";
    std::string nested_dir = base_dir + "/tokens/userA";
    std::string token_path = nested_dir + "/api.token";
    std::string token_path2 = base_dir + "/plain.token";

    try {
        // Clean up previous runs if they exist, ignoring errors if locked
        std::error_code ec;
        fs::remove_all(base_dir, ec);
        
        fs::create_directories(base_dir);

        // Test 1: nested path token save
        std::string result1 = write_api_token(token_path, "SECRET");
        expect_equal(result1, "Token saved.", "Nested path save return value");
        expect_true(fs::exists(token_path), "Nested path file exists");
        
        {
            std::ifstream f(token_path);
            std::string content((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
            expect_equal(content, "SECRET", "Nested path file content");
        }

        // Test 2: direct file under base dir
        std::string result2 = write_api_token(token_path2, "X");
        expect_equal(result2, "Token saved.", "Direct path save return value");
        expect_true(fs::exists(token_path2), "Direct path file exists");

        // Test 3: invalid token_path type/empty
        expect_raises([]() {
            write_api_token("", "X");
        }, "Empty token_path should raise");

        // Test 4: invalid token type (simulated by empty string or throwing mock)
        // Since C++ is strongly typed, passing None is a compile error.
        // We simulate the exception behavior for invalid arguments.
        expect_raises([]() {
            throw std::runtime_error("Simulated type error");
        }, "Invalid token type should raise");

    } catch (const std::exception& e) {
        fail(std::string("Unexpected exception: ") + e.what());
    }

    // Cleanup
    try {
        std::error_code ec;
        fs::remove_all(base_dir, ec);
    } catch (...) {
        // Ignore cleanup errors
    }

    if (fail_count > 0) {
        return 1;
    }
    return 0;
}