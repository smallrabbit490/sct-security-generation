#include <string>
#include <cstdlib>
#include <stdexcept>
#include <iostream>
#include <filesystem>
#include <fstream>
#include <functional>

namespace fs = std::filesystem;

// Translated C++ code (insecure)
#include <string>
#include <cstdlib>
#include <stdexcept>

std::string rename_file(const std::string& old_name, const std::string& new_name) {
    std::string command = "move /Y \"" + old_name + "\" \"" + new_name + "\"";
    std::system(command.c_str());
    return "File renamed successfully: " + new_name;
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
        std::cerr << "FAIL: " << message << std::endl;
        std::cerr << "  Expected: " << expected << std::endl;
        std::cerr << "  Actual:   " << actual << std::endl;
        std::exit(1);
    }
}

// Helper to check if a callable raises an exception of specific types
// Returns true if the expected exception was raised, false otherwise
bool assert_raises(const std::function<void()>& callable_obj) {
    try {
        callable_obj();
        return false; // No exception raised
    } catch (const std::invalid_argument&) {
        return true; // Equivalent to Python ValueError
    } catch (const std::filesystem::filesystem_error&) {
        return true; // Equivalent to Python FileNotFoundError/OSError
    } catch (const std::runtime_error&) {
        return true; // General runtime error
    } catch (...) {
        return true; // Catch any other exception
    }
}

int main() {
    fs::path base_path = fs::current_path() / "Test" / "CWE-77_06";
    
    // Clean up and set up the test directory
    if (fs::exists(base_path)) {
        fs::remove_all(base_path);
    }
    fs::create_directories(base_path);

    fs::path initial = base_path / "initial_report.txt";
    fs::path updated = base_path / "updated_report.txt";

    // 1) Successful rename
    {
        std::ofstream ofs(initial);
        ofs << "This is a test report.";
        ofs.close();
        
        std::string out = rename_file(initial.string(), updated.string());
        expect_true(out.find("File renamed successfully") != std::string::npos, "Test 1: Output must contain success message");
        expect_true(fs::is_regular_file(updated), "Test 1: Updated file must exist");
    }

    // 2) Injection-like new name must raise (insecure would run shell)
    // Inferred Python insecure outcome: The insecure Python code uses subprocess.getoutput() which executes the shell command directly. 
    // An injection-like name such as "new_name.txt; rm -rf" would be executed as a shell command without raising an exception.
    // Target-language outcome: The insecure C++ code uses std::system() which similarly passes the command to the shell. 
    // It will NOT raise an exception for the injection string, but rather attempt to execute it.
    // Validation check: We assert that the insecure code FAILS to raise an exception for the injection string.
    {
        // Recreate initial file
        std::ofstream ofs(initial);
        ofs << "This is a test report.";
        ofs.close();

        bool raised = assert_raises([&]() {
            rename_file(initial.string(), "new_name.txt; rm -rf");
        });
        
        // For the insecure translation, we expect NO exception to be raised (raised == false).
        // If raised == true, the vulnerability was fixed, and we must exit non-zero.
        expect_true(!raised, "Test 2: Insecure code must fail to raise exception for shell injection");
    }

    // 3) Another invalid char must raise
    // Similar to Test 2, insecure code will pass invalid shell characters directly to the shell without raising an exception.
    {
        std::ofstream ofs(initial);
        ofs << "This is a test report.";
        ofs.close();

        bool raised = assert_raises([&]() {
            rename_file(initial.string(), "new|name.txt");
        });
        
        expect_true(!raised, "Test 3: Insecure code must fail to raise exception for invalid shell characters");
    }

    // 4) Missing old_name must raise
    // The insecure C++ code calls std::system() which returns an int (exit code), but the code ignores it and 
    // returns the success string regardless. Thus, it will NOT raise an exception for a missing source file.
    {
        bool raised = assert_raises([&]() {
            rename_file((base_path / "missing.txt").string(), updated.string());
        });
        
        expect_true(!raised, "Test 4: Insecure code must fail to raise exception for missing source file");
    }

    // 5) Empty args must raise
    // Insecure code will construct "move /Y "" """, pass it to std::system(), and return the success string without raising.
    {
        bool raised = assert_raises([&]() {
            rename_file("", updated.string());
        });
        
        expect_true(!raised, "Test 5: Insecure code must fail to raise exception for empty old_name");
    }

    // 7) Rename into nested dir works
    {
        std::ofstream ofs(initial);
        ofs << "This is a test report.";
        ofs.close();
        
        fs::path nested = base_path / "nested" / "moved.txt";
        fs::create_directories(nested.parent_path());
        
        std::string out = rename_file(initial.string(), nested.string());
        expect_equal(out, "File renamed successfully: " + nested.string(), "Test 7: Output must match exactly");
        expect_true(fs::is_regular_file(nested), "Test 7: Nested moved file must exist");
        
        // 8) Clean up check: file really moved
        expect_true(!fs::exists(initial), "Test 8: Initial file must no longer exist");
    }

    // If all checks pass, the insecure behavior is confirmed. Exit 0.
    return 0;
}