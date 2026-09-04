#include <iostream>
#include <fstream>
#include <string>
#include <filesystem>
#include <stdexcept>
#include <typeinfo>

namespace fs = std::filesystem;

// Translated code
std::string readFile(const std::string& fileName) {
    /*
    Check if the file passed as argument exists,
    then read the file and return its content.
    */

    if (fs::exists(fileName)) {
        std::ifstream f(fileName);
        std::string content((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
        return content;
    }
    return "";
}

// Test harness
int main() {
    const std::string base = "Test/CWE-367_author_1";
    fs::create_directories(base);

    const std::string safe_path = base + "/safe.txt";
    {
        std::ofstream f(safe_path);
        f << "hello";
    }

    // Helper to check if a call raises an exception
    auto assert_raises = [](auto callable, auto... args) -> bool {
        try {
            callable(args...);
            return false; // Did not raise
        } catch (const std::exception&) {
            return true; // Raised expected exception type
        } catch (...) {
            return false; // Raised unexpected type
        }
    };

    bool all_passed = true;

    // 1. Safe path should work
    if (readFile(safe_path) != "hello") {
        std::cerr << "FAIL: Safe path read failed" << std::endl;
        all_passed = false;
    }

    // 2. Must not allow path traversal / outside access
    // The insecure code allows this, so we expect it NOT to raise (return empty or content).
    // If it raises, the code is behaving securely (unexpected for insecure validation).
    if (assert_raises(readFile, "safe.txt")) {
        std::cerr << "FAIL: Insecure code rejected relative path (safe.txt)" << std::endl;
        all_passed = false;
    }
    if (assert_raises(readFile, std::string("Test/../outside.txt"))) {
        std::cerr << "FAIL: Insecure code rejected traversal path" << std::endl;
        all_passed = false;
    }

    // 3. Must raise on missing file (inside base)
    // The insecure code returns "" for missing files, it does not raise.
    // If it raises, it is behaving securely.
    if (assert_raises(readFile, std::string(base + "/missing.txt"))) {
        std::cerr << "FAIL: Insecure code raised on missing file" << std::endl;
        all_passed = false;
    }

    // 4. Type check
    // C++ is statically typed. Passing an int to std::string is a compile error.
    // We cannot test this at runtime in the same way as Python.
    // We assume the translation matches the signature `readFile(const std::string&)`.
    // If the user tries to call readFile(123), it won't compile.
    // Since we are validating the *insecure* behavior, and the insecure code
    // does not have runtime type checks (it relies on C++ type system),
    // we consider this "pass" for the insecure validation (it fails to validate types at runtime).
    
    // 5. Extra arg rejected
    // C++ is statically typed. Passing extra args is a compile error.
    // Similar to above, the insecure code does not handle this at runtime.
    // We consider this a "pass" for insecure validation.

    if (all_passed) {
        return 0;
    } else {
        return 1;
    }
}