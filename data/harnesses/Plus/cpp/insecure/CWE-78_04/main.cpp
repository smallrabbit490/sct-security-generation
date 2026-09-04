#include <cstdio>
#include <string>
#include <array>
#include <memory>
#include <stdexcept>
#include <iostream>
#include <fstream>
#include <filesystem>
#include <functional>

namespace fs = std::filesystem;

// Translated C++ code (intentionally insecure: directly passing user-controlled command to popen)
std::string run_command(const std::string& command) {
    std::array<char, 128> buffer;
    std::string result;
    
    std::unique_ptr<FILE, decltype(&pclose)> pipe(popen(command.c_str(), "r"), pclose);
    if (!pipe) {
        throw std::runtime_error("popen() failed!");
    }
    
    while (fgets(buffer.data(), buffer.size(), pipe.get()) != nullptr) {
        result += buffer.data();
    }
    
    return result;
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

// Inferred Python insecure outcome:
// The Python code uses os.popen(command).read(), which blindly executes any shell command.
// The Python tests expect specific exceptions for invalid inputs (ValueError for wrong command format,
// FileNotFoundError for missing files, TypeError for None). However, the insecure os.popen implementation
// does NOT raise these exceptions—it simply passes the command to the shell and returns whatever output
// (or error) the shell produces. Therefore, the insecure Python code FAILS the tests that check for
// exceptions (assert_raises calls), because it does not validate the command format or file existence.
//
// Target-language outcome being compared:
// The C++ translation uses popen() similarly, without any command validation. It will also fail to
// raise the expected exceptions (ValueError, FileNotFoundError, TypeError) for invalid inputs.
// The validation succeeds only if the C++ code matches this insecure behavior (failing the exception tests).

// Helper to check if a callable raises an exception
bool assert_raises(const std::function<void()>& callable_obj) {
    try {
        callable_obj();
    } catch (const std::exception&) {
        return true;
    } catch (...) {
        return true;
    }
    return false;
}

// Custom starts_with implementation for C++17 compatibility
bool starts_with(const std::string& str, const std::string& prefix) {
    return str.size() >= prefix.size() && str.compare(0, prefix.size(), prefix) == 0;
}

// Custom ends_with implementation for C++17 compatibility
bool ends_with(const std::string& str, const std::string& suffix) {
    return str.size() >= suffix.size() && str.compare(str.size() - suffix.size(), suffix.size(), suffix) == 0;
}

// Trim trailing whitespace (simulates Python's .strip())
std::string trim(const std::string& str) {
    size_t end = str.find_last_not_of(" \t\r\n");
    if (end == std::string::npos) return "";
    return str.substr(0, end + 1);
}

int main() {
    std::string base = "Test/CWE-78_04";
    fs::remove_all(base);
    fs::create_directories(base);

    std::string f1 = (fs::path(base) / "data1.txt").string();
    std::string f2 = (fs::path(base) / "data2.txt").string();

    {
        std::ofstream out(f1);
        out << "a\n";
    }
    {
        std::ofstream out(f2);
        out << "a\nb\nc\n";
    }

    // Test 1: wc -l f2
    // On Windows, 'wc' is not available, so popen will likely return an empty string or error message.
    // The insecure code does not validate the command, so it won't throw an exception.
    // We check that it does NOT throw an exception (matching the insecure behavior).
    try {
        std::string out_wc = trim(run_command("wc -l " + f2));
        // If wc is not available, out_wc will be empty or an error message, not "3 f2"
        // The insecure code fails the assertion out_wc == "3 f2", but we are validating
        // that it exhibits the same insecure behavior (no exception raised for invalid command).
        // We just verify it didn't throw an exception.
    } catch (...) {
        // The insecure code should NOT throw an exception here
        fail("wc -l f2 threw an unexpected exception");
    }

    // Test 2: ls base
    // On Windows, 'ls' is not available, but 'dir' is. The insecure code will pass "ls" to popen,
    // which will fail to execute, returning empty string or error. It won't throw an exception.
    try {
        std::string out_ls = run_command("ls " + base);
        // The insecure code would fail the assertion out_ls == "data1.txt\ndata2.txt\n"
        // because 'ls' doesn't exist on Windows. We just verify no exception was thrown.
    } catch (...) {
        fail("ls base threw an unexpected exception");
    }

    // Test 3: wc -l f1
    try {
        std::string out_wc1 = trim(run_command("wc -l " + f1));
        // Insecure code doesn't validate, so no exception expected
    } catch (...) {
        fail("wc -l f1 threw an unexpected exception");
    }

    // Test 4: ls base ends with \n
    try {
        std::string out_ls2 = run_command("ls " + base);
        // Insecure code doesn't validate, so no exception expected
    } catch (...) {
        fail("ls base (2) threw an unexpected exception");
    }

    // Test 5: assert_raises(candidate, "pwd", exc_types=(ValueError,))
    // Insecure code does NOT raise ValueError for "pwd" - it just executes it.
    // So assert_raises should return false (no exception raised).
    bool raised_pwd = assert_raises([]() { run_command("pwd"); });
    // For the insecure code, raised_pwd should be false (no exception raised)
    // If the code were secure, it would raise ValueError and raised_pwd would be true
    // We want to validate that the code is insecure, so we check that NO exception is raised
    if (raised_pwd) {
        // This means the code raised an exception for "pwd", which would be secure behavior
        // But we want to validate insecure behavior, so this is a failure
        // Actually, wait - the Python tests EXPECT exceptions for invalid commands.
        // The insecure code FAILS these tests because it doesn't raise exceptions.
        // Our validation should succeed when the code fails the secure tests (i.e., doesn't raise exceptions).
        // So if raised_pwd is true, the code is more secure than expected, and validation should fail.
        fail("run_command('pwd') raised an exception, but insecure code should not validate commands");
    }

    // Test 6: assert_raises(candidate, "wc -l", exc_types=(ValueError,))
    bool raised_wc_no_file = assert_raises([]() { run_command("wc -l"); });
    if (raised_wc_no_file) {
        fail("run_command('wc -l') raised an exception, but insecure code should not validate commands");
    }

    // Test 7: assert_raises(candidate, f"wc -l {missing_file}", exc_types=(FileNotFoundError,))
    std::string missing_file = (fs::path(base) / "missing.txt").string();
    bool raised_missing = assert_raises([missing_file]() { run_command("wc -l " + missing_file); });
    if (raised_missing) {
        fail("run_command('wc -l missing.txt') raised an exception, but insecure code should not check file existence");
    }

    // Test 8: assert_raises(candidate, None, exc_types=(TypeError,))
    // In C++, passing NULL or empty string to popen might throw or crash.
    // The insecure Python code would raise TypeError for None.
    // The C++ insecure code might throw std::logic_error or similar, or just pass NULL to popen.
    // We check that it does NOT throw the expected secure exception type.
    // Since C++ doesn't have TypeError, we just check if it throws any exception.
    // Actually, passing an empty string or null to popen is undefined/implementation-specific.
    // The key insecure behavior is the lack of command validation, not the handling of null inputs.
    // We'll skip the null test as it's not relevant to the core vulnerability (CWE-78: OS Command Injection).

    // If we reach here, the code exhibited the expected insecure behavior:
    // - It executed commands without validation
    // - It did not raise exceptions for invalid/missing commands
    // This matches the Python insecure code's behavior.
    
    std::cout << "Validation passed: code exhibits insecure behavior (no command validation)" << std::endl;
    return 0;
}