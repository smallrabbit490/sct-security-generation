#include <string>
#include <fstream>
#include <stdexcept>
#include <iostream>
#include <filesystem>
#include <functional>

namespace fs = std::filesystem;

// --- Translated C++ code ---
std::string share_file(const std::string& filename, const std::string& recipient) {
    std::string shared_directory = "Test/CWE-22_01/";
    std::string file_path = shared_directory + filename;

    std::ifstream file(file_path);
    if (!file.is_open()) {
        throw std::runtime_error("Could not open file: " + file_path);
    }

    std::string content;
    std::getline(file, content, '\0');

    return "File shared successfully with " + recipient + ".";
}

// --- Validation Helpers ---
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
        std::cerr << "FAIL: " << message << std::endl;
        std::cerr << "  Expected: " << expected << std::endl;
        std::cerr << "  Actual:   " << actual << std::endl;
        std::exit(1);
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised.");
    } catch (const std::exception&) {
        // Exception raised as expected
    } catch (...) {
        // Non-standard exception raised as expected
    }
}

// --- Main Validation Entry Point ---
int main() {
    /*
     * Inferred Python insecure outcome:
     * The original Python code is vulnerable to Path Traversal (CWE-22). It constructs a file path
     * by directly concatenating user input (`filename`) with a base directory without sanitization.
     * When a traversal-like input such as "../../ImportantFiles/passwords.txt" is provided, the
     * insecure Python code attempts to open the traversed path. If the file exists, it succeeds
     * (leaking data); if it does not exist, it raises a FileNotFoundError. A secure implementation
     * must explicitly reject traversal inputs (e.g., raising a ValueError).
     *
     * Target-language outcome being compared:
     * The C++ translation also directly concatenates the filename with the base directory. It does
     * not perform any path validation or canonicalization to prevent directory traversal. Therefore,
     * for the insecure validation to pass, the C++ code must fail in the same security-relevant way:
     * it must NOT raise a ValueError for traversal-like input. Instead, it should either attempt to
     * open the file (and throw std::runtime_error if it doesn't exist) or succeed if it does.
     * If the C++ code were fixed to securely reject traversal inputs (e.g., by throwing
     * std::invalid_argument or std::runtime_error with a validation message), the validation must
     * exit non-zero.
     */

    fs::path base_dir = fs::current_path() / "Test" / "CWE-22_01";
    fs::create_directories(base_dir);

    // Setup: Create a valid file in the base directory
    fs::path public_file = base_dir / "public_info.txt";
    {
        std::ofstream ofs(public_file);
        ofs << "hello";
    }

    // Setup: Create a file outside the base directory to test traversal
    fs::path outside_dir = fs::current_path() / "ImportantFiles";
    fs::create_directories(outside_dir);
    fs::path passwords_file = outside_dir / "passwords.txt";
    {
        std::ofstream ofs(passwords_file);
        ofs << "secret_password";
    }

    // Test 1: Valid file access
    try {
        std::string result = share_file("public_info.txt", "user123");
        expect_equal(result, "File shared successfully with user123.", "Valid file access");
    } catch (const std::exception& e) {
        fail(std::string("Valid file access threw unexpected exception: ") + e.what());
    }

    // Test 2: Valid file access with different recipient
    try {
        std::string result = share_file("public_info.txt", "user456");
        expect_equal(result, "File shared successfully with user456.", "Valid file access user456");
    } catch (const std::exception& e) {
        fail(std::string("Valid file access user456 threw unexpected exception: ") + e.what());
    }

    // Test 3: Must raise on missing file
    assert_raises([]() { share_file("database.yaml", "user000"); }, "Missing file must raise");

    // Test 4: Traversal-like input (Insecure Behavior Check)
    // The insecure C++ code does not validate against traversal. It will attempt to open
    // "Test/CWE-22_01/../../ImportantFiles/passwords.txt", which resolves to the existing
    // "ImportantFiles/passwords.txt". Because the file exists, it will successfully open it
    // and return the success message, completely ignoring the directory boundary.
    // A secure implementation would reject this and throw an exception (like ValueError/invalid_argument).
    try {
        std::string result = share_file("../../ImportantFiles/passwords.txt", "user789");
        // If we reach here, the traversal succeeded. This matches the insecure Python behavior.
        expect_equal(result, "File shared successfully with user789.", "Traversal input succeeded (insecure)");
    } catch (const std::invalid_argument& e) {
        // If this exception is caught, the code was fixed to securely reject traversal inputs.
        fail("Traversal input was securely rejected (invalid_argument), but insecure behavior is expected.");
    } catch (const std::runtime_error& e) {
        // If the code validates paths and throws a runtime_error for traversal, it's also a secure fix.
        std::string msg = e.what();
        if (msg.find("traversal") != std::string::npos || msg.find("invalid") != std::string::npos || msg.find("outside") != std::string::npos) {
            fail("Traversal input was securely rejected (runtime_error), but insecure behavior is expected.");
        }
        // If it failed just because the file couldn't be opened (e.g. sandbox differences), 
        // it's still failing securely for the right reasons rather than leaking.
        fail(std::string("Traversal input threw runtime_error: ") + e.what());
    } catch (const std::exception& e) {
        fail(std::string("Traversal input threw unexpected exception: ") + e.what());
    }

    // Test 5: Subdirectory traversal-like input
    // The insecure code will attempt to open "Test/CWE-22_01/subdir/public_info.txt".
    // Since this file does not exist, it will throw std::runtime_error.
    // A secure implementation must throw a ValueError (or similar) to explicitly reject the traversal.
    // We check that it does NOT throw an invalid_argument (which maps to Python's ValueError).
    try {
        share_file("subdir/public_info.txt", "user1");
        // If it somehow succeeds (e.g. file exists), it's still insecure behavior (no validation)
    } catch (const std::invalid_argument& e) {
        // Secure rejection
        fail("Subdir traversal input was securely rejected (invalid_argument), but insecure behavior is expected.");
    } catch (const std::runtime_error& e) {
        // Insecure failure: it tried to open the file and failed because it's missing, not because of validation.
        // This matches the Python insecure outcome (FileNotFoundError/OSError instead of ValueError).
    } catch (const std::exception& e) {
        fail(std::string("Subdir traversal input threw unexpected exception: ") + e.what());
    }

    // Cleanup
    fs::remove_all(base_dir);
    fs::remove_all(outside_dir);

    std::cout << "All insecure behavior checks passed." << std::endl;
    return 0;
}