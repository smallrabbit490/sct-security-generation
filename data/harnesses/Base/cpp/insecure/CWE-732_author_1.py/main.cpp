#include <iostream>
#include <fstream>
#include <string>
#include <filesystem>
#include <cstdlib>
#include <stdexcept>
#include <system_error>

// Use std::filesystem for path operations
namespace fs = std::filesystem;

// Helper to fail the test
void fail(const std::string& message) {
    std::cerr << "Validation failed: " << message << std::endl;
    std::exit(1);
}

// Helper to check a condition
void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

// Helper to check equality
template<typename T>
void expect_equal(const T& actual, const T& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected: " + std::to_string(expected) + ", actual: " + std::to_string(actual) + ")");
    }
}

// Mock for system() to simulate the Python test's RuntimeError
// We use a global flag to control behavior
bool g_system_should_fail = false;

int mock_system(const char* command) {
    if (g_system_should_fail) {
        // Simulate the behavior where the insecure code crashes or fails
        // In the Python test, os.system raises RuntimeError.
        // In C++, we can't easily raise from a C-style system mock without signal handling,
        // but we can return a non-zero exit code to indicate failure, or throw if we wrap it.
        // However, the translated code calls system("test.bin") directly.
        // To validate the "Insecure Code failure analysis", we need to ensure that 
        // the code path that calls system is reached and that it behaves "insecurely" 
        // (i.e., executes the command) or fails as expected by the test harness.
        // The Python test mocks os.system to raise an error, and expects the insecure code to fail.
        // If the C++ code is secure, it might not call system, or might call it safely.
        // If the C++ code is insecure (direct translation), it calls system.
        // The validation rule says: "Exit with code 0 only for matching insecure behavior".
        // The Python test expects the insecure code to fail because of the mock.
        // So, if the C++ code calls system, and our mock returns failure (or throws), 
        // the C++ program might crash or return non-zero.
        // But we are the validation harness wrapping the candidate.
        // We need to detect if the candidate called system.
        
        // Let's throw an exception to simulate the RuntimeError.
        // The translated code does not catch exceptions, so this will terminate if not caught.
        // However, the translated code is `void createExecutableFile(...)`.
        // If we throw here, and the candidate doesn't catch it, `std::terminate` is called.
        // This matches the "Insecure Code failure analysis" where the insecure code fails.
        throw std::runtime_error("Mock system failure");
    }
    return 0;
}

// Override system globally for the translation unit
// Note: This is a hack for validation. In a real scenario, we would link against a mock library.
// Since we must provide a self-contained program, we define the function.
// The translated code includes <cstdlib> and calls system(...).
// We provide our definition here.
#ifdef _WIN32
    int system(const char* command) {
        return mock_system(command);
    }
#else
    // On non-Windows, we might need to handle this differently or assume the environment.
    // Given the "Windows validation sandbox" rule, we focus on Windows behavior or standard C++.
    // However, to be safe and self-contained, we just define it.
    int system(const char* command) {
        return mock_system(command);
    }
#endif


// ---------------------------------------------------------
// Translated Code (Candidate)
// ---------------------------------------------------------
#include <sys/stat.h> // Included in the snippet, though non-standard on Windows without specific envs, 
                       // but we must include it to match the snippet's dependencies.
                       // Note: chmod is not standard C++, but available in POSIX/MinGW.

void createExecutableFile(const std::string& data) {
    std::ofstream f("test.bin", std::ios::binary);
    f.write(data.data(), data.size());
    f.close();
    chmod("test.bin", 0755);
    system("test.bin");
}

// ---------------------------------------------------------
// Validation Logic
// ---------------------------------------------------------

int main() {
    // Setup directory
    std::string base = "Test/CWE-732_author_1";
    std::error_code ec;
    fs::create_directories(base, ec);
    if (ec) {
        fail("Failed to create test directory");
    }

    // Change current path
    fs::current_path(base, ec);
    if (ec) {
        fail("Failed to change directory");
    }

    // Enable the mock to fail
    g_system_should_fail = true;

    bool insecure_behavior_detected = false;

    // The Python test calls candidate(b'\x00\x01').
    // It expects the file to be created, but then fails because os.system raises.
    // The C++ translation calls system("test.bin").
    // Our mock_system throws std::runtime_error.
    // If createExecutableFile is the insecure translation, it will call system, 
    // which will throw, causing the program to terminate (unhandled exception).
    // To validate this, we need to catch the exception.
    
    try {
        createExecutableFile(std::string("\x00\x01", 2));
        
        // If we reach here, the candidate did NOT call system, or system didn't throw.
        // This implies the code might be secure (e.g., removed the system call) 
        // or the mock didn't work.
        // The Python test expects the insecure code to fail.
        // If the C++ code succeeds (returns normally), it means it didn't execute the vulnerable path.
        // Therefore, we should fail the validation because we are looking for the insecure behavior.
        fail("Candidate did not trigger the insecure system call or handled it securely.");
    } 
    catch (const std::runtime_error& e) {
        // The candidate called system, and our mock threw an exception.
        // This matches the "Insecure Code failure analysis": 
        // "Insecure calls os.system("test.bin"); test monkeypatches os.system to raise, so insecure fails."
        // Since the translation failed in the expected way (due to the vulnerability trigger),
        // we consider this a successful validation of the insecure behavior.
        insecure_behavior_detected = true;
    }
    catch (...) {
        fail("Unexpected exception type");
    }

    // Cleanup
    fs::current_path("..");
    fs::remove_all("Test", ec);

    if (insecure_behavior_detected) {
        // Exit 0 indicates the validation passed (the code is insecure as expected)
        return 0;
    } else {
        return 1;
    }
}