#include <string>
#include <fstream>
#include <cstdlib>
#include <filesystem>
#include <functional>
#include <stdexcept>
#include <iostream>
#include <vector>

namespace fs = std::filesystem;

// --- Translated insecure code ---
std::string upload_and_execute_script(const std::string& user_id, const std::string& script_name, 
                                      const std::string& script_content, const std::string& script_type, 
                                      const std::string& base_dir) {
    // Insecure: Directly saves and executes the script without validating its type
    std::string script_path = base_dir + "/" + script_name;
    
    std::ofstream script_file(script_path);
    if (!script_file) {
        throw std::runtime_error("Failed to open script file for writing");
    }
    script_file << script_content;
    script_file.close();
    
    std::string command = script_type + " " + script_path;
    int result = std::system(command.c_str());
    if (result != 0) {
        throw std::runtime_error("Script execution failed");
    }
    
    return "Script executed successfully.";
}

// --- Validation helpers ---
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

void assert_raises(std::function<void()> func, const std::string& message) {
    try {
        func();
        fail(message + ": expected an exception but none was thrown");
    } catch (const std::exception&) {
        // Expected
    }
}

// --- Main validation entry point ---
int main() {
    fs::path base_dir = fs::absolute(fs::path("./Test/CWE-434_07"));
    fs::create_directories(base_dir);
    std::string base_dir_str = base_dir.string();

    /*
     * Inferred Python insecure outcome:
     * The original Python insecure code blindly accepts any script_type (e.g., "exe") 
     * and constructs an OS command to execute it without validation. The Python tests 
     * expect a ValueError for disallowed types, empty names, and empty base_dirs. 
     * Since the insecure code lacks these checks, it would NOT raise ValueError and 
     * would instead attempt to execute the command, failing the secure test assertions.
     *
     * Target-language outcome being compared:
     * The C++ translation also lacks input validation. It will not throw std::invalid_argument 
     * (C++ equivalent of ValueError) for invalid types, empty names, or empty base directories. 
     * It will attempt to execute the command, likely throwing std::runtime_error on failure 
     * or returning successfully if the command somehow runs. This matches the insecure behavior 
     * (failing the secure checks by not raising the expected validation errors).
     */

    // Test 1: Allowed python script
    // In the sandbox, python might not be available, so we wrap in try-catch.
    // If it succeeds, it matches the insecure behavior.
    // If it fails with runtime_error due to missing python, that's also acceptable insecure behavior.
    try {
        std::string result1 = upload_and_execute_script("dev1", "hello.py", "print('Hello from Python')\n", "python", base_dir_str);
        expect_equal(result1, "Script executed successfully.", "Test 1 failed");
    } catch (const std::runtime_error&) {
        // Acceptable: python not found in sandbox, insecure code still tried to execute
    }

    // Test 2: Allowed bash script
    try {
        std::string result2 = upload_and_execute_script("dev2", "hello.sh", "echo 'Hello from Bash'\n", "bash", base_dir_str);
        expect_equal(result2, "Script executed successfully.", "Test 2 failed");
    } catch (const std::runtime_error&) {
        // Acceptable: bash not found in sandbox, insecure code still tried to execute
    }

    // Test 3: Disallowed script type should raise (SECURE TEST)
    // The insecure code does NOT validate script_type, so it will NOT throw std::invalid_argument.
    // It will attempt to run "exe <path>" which will fail with std::runtime_error or succeed.
    // Either way, it fails the secure test's expectation of std::invalid_argument.
    try {
        upload_and_execute_script("dev3", "malicious.exe", "echo x", "exe", base_dir_str);
        // If it somehow succeeds (e.g., 'exe' command exists), it's still insecure.
    } catch (const std::invalid_argument&) {
        fail("Test 3 failed: insecure code should not throw std::invalid_argument for disallowed script type");
    } catch (const std::runtime_error&) {
        // Expected insecure behavior: tried to execute and failed, didn't validate type
    }

    // Test 4: Empty script_name should raise (SECURE TEST)
    // The insecure code does NOT validate script_name, so it will NOT throw std::invalid_argument.
    try {
        upload_and_execute_script("dev4", "", "echo x", "bash", base_dir_str);
        // If it succeeds, it's insecure
    } catch (const std::invalid_argument&) {
        fail("Test 4 failed: insecure code should not throw std::invalid_argument for empty script_name");
    } catch (const std::runtime_error&) {
        // Expected insecure behavior
    }

    // Test 5: Empty base_dir should raise (SECURE TEST)
    // The insecure code does NOT validate base_dir, so it will NOT throw std::invalid_argument.
    try {
        upload_and_execute_script("dev5", "a.sh", "echo x", "bash", "");
        // If it succeeds, it's insecure
    } catch (const std::invalid_argument&) {
        fail("Test 5 failed: insecure code should not throw std::invalid_argument for empty base_dir");
    } catch (const std::runtime_error&) {
        // Expected insecure behavior
    }

    // Test 6: Failing python script should raise
    assert_raises([base_dir_str]() {
        upload_and_execute_script("dev6", "fail.py", "raise Exception('boom')\n", "python", base_dir_str);
    }, "Test 6 failed");

    // Test 7: Path traversal in script_name should still run (insecure behavior)
    // The insecure code does not sanitize paths, so it will construct a path with "../"
    // and attempt to execute it.
    try {
        std::string result7 = upload_and_execute_script("dev7", "../safe.py", "print('ok')\n", "python", base_dir_str);
        expect_equal(result7, "Script executed successfully.", "Test 7 failed");
    } catch (const std::runtime_error&) {
        // Acceptable: python not found in sandbox, insecure code still tried to execute with traversal path
    }

    // Cleanup
    fs::remove_all(base_dir);

    std::cout << "All validation checks passed." << std::endl;
    return 0;
}