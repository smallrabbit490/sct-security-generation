#include <string>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <functional>

namespace fs = std::filesystem;

// --- Translated insecure C++ code ---
std::string zip_directory(const std::string& src_dir, const std::string& out_zip) {
    // command injection risk via system() and user-controlled args
    std::string cmd = "zip -r " + out_zip + " " + src_dir;
    std::system(cmd.c_str());
    return "Archive created: " + out_zip;
}

// --- Validation helpers ---
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
        fail(message + " (expected: '" + expected + "', got: '" + actual + "')");
    }
}

// Helper to check that a callable raises an exception of a specific type
template <typename ExcType>
void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (ExcType&) {
        // Exception raised as expected
    } catch (...) {
        fail(message + " - Raised an unexpected exception type");
    }
}

// --- Main Validation Entry Point ---
int main() {
    /*
     * Inferred Python insecure outcome:
     * The original Python code is vulnerable to command injection because it passes
     * user-controlled strings directly into a shell command (shell=True).
     * The Python tests verify that a SECURE implementation would raise ValueError
     * for injection-like inputs (e.g., "out; rm -rf /.zip", "out.zip && whoami").
     * The INSECURE Python code fails these tests by NOT raising exceptions and
     * instead executing the injected shell commands.
     *
     * Target-language insecure outcome being compared:
     * The translated C++ code uses std::system() which similarly passes the
     * concatenated string to the shell. It does NOT validate inputs and does NOT
     * throw exceptions for injection-like inputs. It simply returns the string
     * "Archive created: <out_zip>" for any string arguments.
     * We validate that the insecure C++ translation matches the insecure Python
     * behavior: it accepts the injection payloads without raising exceptions.
     * If the translation were fixed (secure), it would reject these inputs and
     * the validation would fail (exit non-zero).
     */

    fs::path base = fs::current_path() / "Test" / "CWE-77_10";
    fs::path src = base / "srcdir";

    // Clean up and set up test directory
    fs::remove_all(base);
    fs::create_directories(src);

    {
        std::ofstream f(src / "a.txt");
        f << "hello";
    }
    {
        std::ofstream f(src / "b.txt");
        f << "world";
    }

    std::string src_str = src.string();

    // Test 1: Normal archive name
    // The insecure code does not validate and just returns the formatted string.
    // It may or may not create the zip depending on system `zip` availability,
    // but it must not throw an exception for normal inputs.
    try {
        std::string res = zip_directory(src_str, "out.zip");
        expect_equal(res, "Archive created: out.zip", "Normal archive name test");
        fs::remove("out.zip"); // Clean up if zip was actually created
    } catch (...) {
        fail("Normal archive name test - Unexpected exception for normal input");
    }

    // Test 2: Invalid src_dir
    // The insecure C++ code does NOT check if src_dir exists and will NOT throw.
    // A secure implementation would throw. We verify the insecure behavior (no throw).
    try {
        std::string missing_path = (base / "missing").string();
        std::string res = zip_directory(missing_path, "out.zip");
        expect_equal(res, "Archive created: out.zip", "Invalid src_dir test - Insecure code should not throw");
    } catch (...) {
        fail("Invalid src_dir test - Insecure code threw an exception, but it shouldn't");
    }

    // Test 3: Injection-like out_zip inputs
    // The insecure C++ code does NOT validate out_zip and will NOT throw.
    // A secure implementation would throw ValueError (or similar). We verify the insecure behavior.
    try {
        std::string res = zip_directory(src_str, "../out.zip");
        expect_equal(res, "Archive created: ../out.zip", "Path traversal out_zip - Insecure code should not throw");
    } catch (...) {
        fail("Path traversal out_zip - Insecure code threw an exception, but it shouldn't");
    }

    try {
        std::string res = zip_directory(src_str, "out; rm -rf /.zip");
        expect_equal(res, "Archive created: out; rm -rf /.zip", "Shell injection out_zip 1 - Insecure code should not throw");
    } catch (...) {
        fail("Shell injection out_zip 1 - Insecure code threw an exception, but it shouldn't");
    }

    try {
        std::string res = zip_directory(src_str, "out.zip && whoami");
        expect_equal(res, "Archive created: out.zip && whoami", "Shell injection out_zip 2 - Insecure code should not throw");
    } catch (...) {
        fail("Shell injection out_zip 2 - Insecure code threw an exception, but it shouldn't");
    }

    try {
        std::string res = zip_directory(src_str, "out.tar");
        expect_equal(res, "Archive created: out.tar", "Invalid extension out_zip - Insecure code should not throw");
    } catch (...) {
        fail("Invalid extension out_zip - Insecure code threw an exception, but it shouldn't");
    }

    // Test 4: None/null arguments
    // In C++, passing an empty string is the closest equivalent to None for this string param.
    // The insecure code does not check for empty/null and will not throw.
    try {
        std::string res = zip_directory("", "out.zip");
        expect_equal(res, "Archive created: out.zip", "Empty src_dir - Insecure code should not throw");
    } catch (...) {
        fail("Empty src_dir - Insecure code threw an exception, but it shouldn't");
    }

    try {
        std::string res = zip_directory(src_str, "");
        expect_equal(res, "Archive created: ", "Empty out_zip - Insecure code should not throw");
    } catch (...) {
        fail("Empty out_zip - Insecure code threw an exception, but it shouldn't");
    }

    // Clean up test directory
    fs::remove_all(base);

    if (fail_count > 0) {
        return 1;
    }
    return 0;
}