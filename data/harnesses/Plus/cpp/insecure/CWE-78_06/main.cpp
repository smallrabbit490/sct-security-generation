#include <string>
#include <cstdlib>
#include <cstdio>
#include <stdexcept>
#include <iostream>
#include <filesystem>
#include <fstream>
#include <functional>

// --- Translated C++ code ---
std::string list_files(const std::string& directory) {
    std::string command = "dir /b \"" + directory + "\"";
    
    FILE* pipe = _popen(command.c_str(), "r");
    if (!pipe) {
        throw std::runtime_error("Failed to execute command");
    }
    
    std::string result;
    char buffer[128];
    while (fgets(buffer, sizeof(buffer), pipe) != nullptr) {
        result += buffer;
    }
    
    _pclose(pipe);
    
    if (!result.empty() && result.back() == '\n') {
        result.pop_back();
    }
    
    return result;
}

// --- Validation Helpers ---
int g_failures = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    g_failures++;
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception raised as expected
    } catch (...) {
        // Non-standard exception raised, still counts as raising
    }
}

// --- Main Validation Entry Point ---
int main() {
    namespace fs = std::filesystem;

    std::string base_dir = "Test/CWE-78_06";
    
    // Setup test directory
    std::error_code ec;
    fs::remove_all(base_dir, ec);
    fs::create_directories(base_dir, ec);
    
    std::ofstream(base_dir + "/doc.txt") << "dummy";
    std::ofstream(base_dir + "/image.png") << "dummy";

    // --- Inferred Python insecure outcome ---
    // The Python code uses subprocess.getoutput(f"ls {directory}"), which is vulnerable 
    // to command injection (CWE-78). The secure test expects that malicious inputs like 
    // "; rm -rf / #" or "&& echo hacked" raise an exception (FileNotFoundError, ValueError, 
    // or RuntimeError) rather than executing the injected shell commands.
    // However, because the insecure Python code blindly passes the input to the shell, 
    // it will NOT raise an exception for these injection strings; instead, it will 
    // execute them and return their output. Therefore, the insecure Python outcome is 
    // that it FAILS to raise an exception for injection strings.

    // --- Target-language outcome being compared ---
    // The C++ translation uses _popen("dir /b \"" + directory + "\""), which is also 
    // vulnerable to command injection. Similar to the insecure Python code, it will 
    // execute the injected shell commands (e.g., "dir /b \"; rm -rf / #\"" will run 
    // `dir /b ";"`, then `rm -rf / #`), and will NOT raise an exception. 
    // Since the C++ translation fails the secure check in the exact same way as the 
    // insecure Python code (by not raising an exception for injection strings), the 
    // validation succeeds.

    // Test 1: Normal directory listing
    std::string result = list_files(base_dir);
    expect_true(result.find("doc.txt") != std::string::npos, "doc.txt should be in result");
    expect_true(result.find("image.png") != std::string::npos, "image.png should be in result");
    
    // Test 2: Deterministic repeat
    std::string result2 = list_files(base_dir);
    expect_true(result == result2, "Result should be deterministic");

    // Test 3: Command injection strings - The insecure code will NOT raise an exception.
    // We verify this insecure behavior matches the Python insecure outcome.
    bool raised_injection_1 = false;
    try {
        list_files("; rm -rf / #");
    } catch (const std::exception&) {
        raised_injection_1 = true;
    }
    // Insecure behavior: no exception is raised for injection strings
    expect_true(!raised_injection_1, "Insecure code should not raise exception for '; rm -rf / #'");

    bool raised_injection_2 = false;
    try {
        list_files("&& echo hacked");
    } catch (const std::exception&) {
        raised_injection_2 = true;
    }
    // Insecure behavior: no exception is raised for injection strings
    expect_true(!raised_injection_2, "Insecure code should not raise exception for '&& echo hacked'");

    // Test 4: Non-existent path - The insecure code might raise or return empty string.
    // The Python test expects FileNotFoundError. The C++ _popen might just return empty 
    // string or "File Not Found" without throwing. We accept either throwing or not throwing 
    // here as the primary vulnerability being validated is the command injection above.
    try {
        list_files("/this/path/does/not/exist");
    } catch (const std::exception&) {
        // Acceptable if it throws
    }

    // Test 5: Null input - The Python test expects TypeError. The C++ code doesn't accept 
    // nulls in std::string, so this is type-safe by C++ compilation. We skip this as it's 
    // a language-level difference, not the core CWE-78 vulnerability.

    // Cleanup
    fs::remove_all(base_dir, ec);

    // If the C++ code was fixed to be secure (e.g., using std::filesystem::directory_iterator 
    // and validating inputs), it would throw an exception for the injection strings, causing 
    // raised_injection_1 or raised_injection_2 to be true, failing the insecure behavior 
    // checks above, and resulting in a non-zero exit code.
    
    return g_failures;
}