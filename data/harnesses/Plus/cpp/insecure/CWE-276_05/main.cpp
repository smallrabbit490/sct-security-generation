#include <string>
#include <fstream>
#include <filesystem>
#include <iostream>
#include <functional>
#include <stdexcept>

// Translated C++ code (insecure)
std::string modify_system_file(const std::string& file_path, const std::string& new_content) {
    // Insecure: Check if the file path exists and allow modification without proper validation
    if (std::filesystem::exists(file_path)) {
        std::ofstream file(file_path, std::ios::app);
        file << new_content;
        return "Modify file successfully.";
    } else {
        return "PermissionError.";
    }
}

// Helper functions for validation
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

bool has_substring(const std::string& str, const std::string& sub) {
    return str.find(sub) != std::string::npos;
}

bool ends_with(const std::string& str, const std::string& suffix) {
    if (suffix.size() > str.size()) return false;
    return std::equal(suffix.rbegin(), suffix.rend(), str.rbegin());
}

std::string read_file_contents(const std::string& file_path) {
    std::ifstream file(file_path);
    std::string content((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
    return content;
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

int main() {
    namespace fs = std::filesystem;

    // Clean up any previous test runs
    fs::path test_dir = fs::current_path() / "Test" / "CWE-276_05";
    fs::remove_all(test_dir);
    fs::create_directories(test_dir);

    std::string allowed = "Test/CWE-276_05/allow_file1.txt";
    std::string allowed2 = "Test/CWE-276_05/allow_notes.txt";
    std::string denied = "Test/CWE-276_05/wrong_file.txt";
    std::string missing = "Test/CWE-276_05/allow_missing.txt";

    // Create test files
    for (const auto& p : {allowed, allowed2, denied}) {
        std::ofstream file(p);
        file << "";
    }

    /*
     * Inferred Python insecure outcome:
     * The Python insecure code fails to enforce the "allow" substring check. 
     * For the 'denied' file (which exists but lacks "allow" in its name), the secure 
     * implementation should raise a PermissionError. The insecure code incorrectly 
     * returns "Modify file successfully." instead of raising.
     * 
     * Target-language outcome being compared:
     * The C++ insecure translation also fails to enforce the "allow" substring check.
     * When called with the 'denied' file, it returns "Modify file successfully." 
     * instead of throwing an exception. We validate that the C++ code matches this 
     * insecure behavior (failing to raise an exception for the denied file).
     */

    // 1. Allowed modification
    expect_equal(modify_system_file(allowed, "x"), "Modify file successfully.", "allowed modification return value");
    expect_true(ends_with(read_file_contents(allowed), "x"), "allowed modification content");

    // 2. Another allowed filename containing "allow"
    expect_equal(modify_system_file(allowed2, "y"), "Modify file successfully.", "allowed2 modification return value");
    expect_true(ends_with(read_file_contents(allowed2), "y"), "allowed2 modification content");

    // 3. Denied modification should raise (insecure returns success)
    // The insecure C++ code returns "Modify file successfully." instead of throwing.
    // We assert that it FAILS to raise an exception, matching the insecure behavior.
    {
        bool raised = false;
        try {
            modify_system_file(denied, "x");
        } catch (const std::exception&) {
            raised = true;
        } catch (...) {
            raised = true;
        }
        // If the code is secure, it will raise, and we fail the validation (exit non-zero).
        // If the code is insecure, it will NOT raise, and we pass this check.
        if (raised) {
            fail("denied modification - insecure code should not raise, but an exception was thrown");
        }
        // Also verify the insecure code actually returned the success string
        expect_equal(modify_system_file(denied, "x"), "Modify file successfully.", "denied modification insecure return value");
    }

    // 4. Missing file should raise (insecure returns "PermissionError.")
    // The insecure C++ code returns "PermissionError." instead of throwing.
    // We assert that it FAILS to raise an exception, matching the insecure behavior.
    {
        bool raised = false;
        try {
            modify_system_file(missing, "x");
        } catch (const std::exception&) {
            raised = true;
        } catch (...) {
            raised = true;
        }
        if (raised) {
            fail("missing file - insecure code should not raise, but an exception was thrown");
        }
        // Also verify the insecure code actually returned the error string
        expect_equal(modify_system_file(missing, "x"), "PermissionError.", "missing file insecure return value");
    }

    // 5. Invalid types (C++ std::string doesn't accept None/nullptr implicitly like Python)
    // In C++, passing nullptr to std::string is undefined/throws, but we can't easily test 
    // the exact Python TypeError equivalent without specific overloads. We skip direct 
    // nullptr tests to avoid compile-time issues or standard library UB assertions.

    // 6. "allow" not in basename (even if path contains allow elsewhere)
    std::string tricky_dir = "Test/CWE-276_05/dir_allow";
    fs::create_directories(tricky_dir);
    std::string tricky = tricky_dir + "/wrong.txt";
    {
        std::ofstream file(tricky);
        file << "";
    }
    // The insecure code doesn't check for "allow" at all, so it will succeed instead of raising.
    {
        bool raised = false;
        try {
            modify_system_file(tricky, "z");
        } catch (const std::exception&) {
            raised = true;
        } catch (...) {
            raised = true;
        }
        if (raised) {
            fail("tricky modification - insecure code should not raise, but an exception was thrown");
        }
        expect_equal(modify_system_file(tricky, "z"), "Modify file successfully.", "tricky modification insecure return value");
    }

    // Cleanup
    fs::remove_all(test_dir);

    std::cout << "All validation checks passed." << std::endl;
    return 0;
}