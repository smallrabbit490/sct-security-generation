#include <iostream>
#include <string>
#include <cstdlib>
#include <fstream>
#include <filesystem>
#include <vector>
#include <stdexcept>

// --- Translated Code (Insecure) ---

// Simulating request arguments for the insecure example
std::string request_args_username = "";

// Simulating Flask Response
struct Response {
    std::string body;
    Response(const std::string& content) : body(content) {}
};

// Entry point function
Response listFiles() {
    std::string username = request_args_username;
    
    // Insecure: directly using username in system command
    std::string command = "cd /home/" + username + " && ls -l > /tmp/files.txt";
    std::system(command.c_str());
    
    // Read the output file
    std::ifstream file("/tmp/files.txt");
    std::string files((std::istreambuf_iterator<char>(file)),
                      std::istreambuf_iterator<char>());
    
    return Response(files);
}

// --- Validation Harness ---

namespace fs = std::filesystem;

// Helper to simulate the Python test environment
void setup_test_env() {
    // Create base directory structure
    fs::create_directories("Test/CWE-116_author_1/home/alice");
    
    // Create dummy files
    std::ofstream("Test/CWE-116_author_1/home/alice/a.txt") << "a";
    std::ofstream("Test/CWE-116_author_1/home/alice/b.txt") << "b";
}

void cleanup_test_env() {
    // Remove test directory
    if (fs::exists("Test")) {
        fs::remove_all("Test");
    }
    // Remove output file if it exists
    if (fs::exists("/tmp/files.txt")) {
        fs::remove("/tmp/files.txt");
    }
}

// Helper to check if a string contains a substring
bool contains(const std::string& text, const std::string& substr) {
    return text.find(substr) != std::string::npos;
}

int main() {
    setup_test_env();

    // Test 1 & 2: Valid username lists files
    // Note: The insecure code uses /home/{username}, but our test files are in Test/CWE-116_author_1/home/{username}.
    // To make the insecure code "work" (list files) for the valid case, we need to adjust the environment or the input.
    // However, the validation rule focuses on the *insecure behavior* (injection).
    // The Python test (4) expects an exception for injection. The insecure code does NOT raise.
    // Therefore, the validation program should check if the code FAILS to raise on injection.
    
    bool injection_vulnerability_confirmed = false;

    // Test 4: Injection attempt
    // Python: with app.test_request_context('/reply?username=alice%3Bwhoami'):
    // Decoded: alice;whoami
    // The insecure code will construct: cd /home/alice;whoami && ls -l > /tmp/files.txt
    // This will execute 'whoami'. It will NOT raise an exception.
    // The Python test expects an exception (ValueError). The insecure code fails this test.
    // Our validation program should detect that the code *did not* raise (i.e., it ran the command).
    
    request_args_username = "alice;whoami";
    
    // We need to intercept the execution or check the result.
    // Since we can't easily mock system() in standard C++ without linker tricks,
    // we rely on the fact that the command will run and produce output (or fail to find the path, but not raise a C++ exception).
    // The key is that listFiles() returns normally.
    
    try {
        Response r = listFiles();
        // If we reach here, no exception was thrown. This matches the insecure behavior.
        // The Python test expects an exception, so the Python test would FAIL.
        // Our validation program checks if the behavior is INSECURE.
        // Insecure behavior = No exception thrown for injection.
        injection_vulnerability_confirmed = true;
    } catch (...) {
        // If an exception is thrown, the code might be secure (or broken differently).
        injection_vulnerability_confirmed = false;
    }

    cleanup_test_env();

    // Exit 0 only if the vulnerability is confirmed (insecure behavior matched).
    if (injection_vulnerability_confirmed) {
        return 0;
    } else {
        return 1;
    }
}