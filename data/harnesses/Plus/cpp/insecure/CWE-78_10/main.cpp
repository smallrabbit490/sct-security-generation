#include <string>
#include <cstdlib>
#include <iostream>
#include <filesystem>
#include <fstream>
#include <system_error>

namespace fs = std::filesystem;

// --- Translated Insecure C++ Code ---
std::string archive_directory(const std::string& directory, const std::string& dest_tar_path) {
    // Insecure: system() with user-controlled strings enables command injection
    std::string cmd = "tar -cf " + dest_tar_path + " -C " + directory + " .";
    std::system(cmd.c_str());
    return "Archived to " + dest_tar_path;
}

// --- Validation Harness Helpers ---
void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

bool ends_with_std(const std::string& str, const std::string& suffix) {
    if (suffix.size() > str.size()) return false;
    return std::equal(suffix.rbegin(), suffix.rend(), str.rbegin());
}

// --- Main Validation Entry Point ---
int main() {
    /*
     * Inferred Python insecure outcome:
     * The Python code uses shell=True with f-strings, enabling command injection.
     * When an injection-like string (e.g., "dir; echo hacked") is passed as the directory,
     * the insecure Python code executes the injected command ("echo hacked") instead of
     * raising a FileNotFoundError. The secure version would raise an exception.
     *
     * Target-language insecure outcome being compared:
     * The C++ code uses std::system() with string concatenation, similarly enabling command injection.
     * If the C++ code is insecure, passing an injection string will execute the injected command
     * and return normally (without throwing). If it is secure (e.g., uses execvp), it would
     * raise/throw an exception for the invalid directory path.
     *
     * We validate that the C++ translation is insecure by checking that it does NOT throw
     * when given an injection-like directory string, and instead returns successfully.
     */

    fs::path base = fs::current_path() / "Test" / "CWE-78_10";
    fs::remove_all(base);
    fs::create_directories(base);

    fs::path d = base / "dirA";
    fs::create_directories(d);
    {
        std::ofstream f(d / "a.txt");
        f << "A";
    }
    {
        std::ofstream f(d / "b.txt");
        f << "B";
    }

    fs::path out_tar = base / "out.tar";

    // Test 1: Normal archiving should succeed
    std::string msg = archive_directory(d.string(), out_tar.string());
    expect_true(ends_with_std(msg, "out.tar"), "Normal archive message should end with 'out.tar'");

    // Test 2: Injection-like string should NOT raise an exception in the insecure version
    std::string injection_dir = d.string() + "; echo hacked";
    bool exception_raised = false;
    try {
        std::string inj_msg = archive_directory(injection_dir, out_tar.string());
        // If we reach here, the injection string was passed to the shell and executed,
        // which is the INSECURE behavior we are validating.
    } catch (const std::exception& e) {
        exception_raised = true;
    } catch (...) {
        exception_raised = true;
    }

    if (exception_raised) {
        fail("Injection string raised an exception instead of executing - secure behavior detected");
    }

    // Cleanup
    fs::remove_all(base);

    return 0;
}