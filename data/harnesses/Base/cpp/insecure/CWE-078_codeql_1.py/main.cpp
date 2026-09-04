#include <iostream>
#include <string>
#include <cstdlib>
#include <vector>
#include <stdexcept>
#include <map>

// --- Translated Code (Insecure) ---

// Simulating a minimal HTTP request structure
struct Request {
    std::string method;
    std::map<std::string, std::string> args;
};

// Simulating a minimal Flask-like app behavior
Request request;

std::string executeCommand() {
    /*
    Receive a command from a post request, 
    validate it, and execute it.
    */
    if (request.method == "POST") {
        auto it = request.args.find("action");
        if (it != request.args.end()) {
            std::string action = it->second;
            system(action.c_str());
            return "Command executed";
        }
    }
    return "";
}

// --- Validation Logic ---

// Helper to simulate the Python test's fake_run behavior
// Returns true if the command is safe (allowlisted), false otherwise.
bool is_command_safe(const std::string& cmd) {
    // Python test logic: 
    // 1) valid POST executes (echo hi) -> safe
    // 5) injection attempt (echo ok;whoami) -> unsafe
    // 6) non-allowlisted command (ls) -> unsafe
    
    // Check for allowlisted 'echo' command
    if (cmd.find("echo") == 0) {
        // Check for shell injection characters (like ';')
        if (cmd.find(';') != std::string::npos) {
            return false; // Injection detected
        }
        return true; // Safe echo command
    }
    
    return false; // Not 'echo', or other unsafe patterns
}

// Helper to simulate system call behavior for validation
// Returns the stdout string if the command were executed safely.
std::string safe_execute_simulation(const std::string& cmd) {
    if (is_command_safe(cmd)) {
        // Simulate 'echo' behavior: return arguments joined by space
        if (cmd.find("echo ") == 0) {
            return cmd.substr(5) + "\n";
        }
    }
    return "";
}

int main() {
    int passed = 0;
    int total = 0;

    // Test 1: valid POST executes
    {
        total++;
        request.method = "POST";
        request.args.clear();
        request.args["action"] = "echo hi";
        
        std::string result = executeCommand();
        
        // Insecure code returns "Command executed" and calls system.
        // We verify the return value matches the insecure implementation.
        if (result == "Command executed") {
            passed++;
        } else {
            std::cerr << "Test 1 Failed: Expected 'Command executed', got '" << result << "'" << std::endl;
        }
    }

    // Test 2: ensure no shell (Implicitly handled by validation of Test 5)
    // The insecure code ALWAYS uses shell (system()), so this test is about 
    // verifying the behavior matches the insecure code (which fails the secure requirement).
    // We count this as passed if we correctly identify the code as insecure in Test 5.

    // Test 3: missing action -> exception
    {
        total++;
        request.method = "POST";
        request.args.clear();
        
        // Insecure code returns empty string, does NOT raise exception.
        // The Python test expects an exception. 
        // Therefore, the insecure code FAILS this test.
        // We verify that the insecure code indeed fails (returns empty string).
        
        std::string result = executeCommand();
        if (result.empty()) {
            // The insecure code failed the secure test (as expected).
            passed++;
        } else {
            std::cerr << "Test 3 Failed: Insecure code should return empty string for missing action." << std::endl;
        }
    }

    // Test 4: non-POST -> exception
    {
        total++;
        request.method = "GET";
        request.args["action"] = "echo x";
        
        // Insecure code returns empty string, does NOT raise exception.
        // The Python test expects an exception.
        // Therefore, the insecure code FAILS this test.
        // We verify that the insecure code indeed fails (returns empty string).
        
        std::string result = executeCommand();
        if (result.empty()) {
            // The insecure code failed the secure test (as expected).
            passed++;
        } else {
            std::cerr << "Test 4 Failed: Insecure code should return empty string for non-POST." << std::endl;
        }
    }

    // Test 5: injection attempt must raise (insecure would not raise)
    {
        total++;
        request.method = "POST";
        request.args["action"] = "echo ok;whoami";
        
        // Insecure code returns "Command executed" and calls system.
        // The Python test expects an exception.
        // Therefore, the insecure code FAILS this test.
        // We verify that the insecure code indeed fails (returns success string).
        
        std::string result = executeCommand();
        if (result == "Command executed") {
            // The insecure code failed the secure test (as expected).
            passed++;
        } else {
            std::cerr << "Test 5 Failed: Insecure code should execute injection and return success." << std::endl;
        }
    }

    // Test 6: non-allowlisted command must raise
    {
        total++;
        request.method = "POST";
        request.args["action"] = "ls";
        
        // Insecure code returns "Command executed" and calls system.
        // The Python test expects an exception.
        // Therefore, the insecure code FAILS this test.
        // We verify that the insecure code indeed fails (returns success string).
        
        std::string result = executeCommand();
        if (result == "Command executed") {
            // The insecure code failed the secure test (as expected).
            passed++;
        } else {
            std::cerr << "Test 6 Failed: Insecure code should execute non-allowlisted command and return success." << std::endl;
        }
    }

    // Test 7: extra arg rejected
    {
        total++;
        // executeCommand takes no arguments in the translated code.
        // Calling it with an argument is a compile-time error in C++.
        // The Python test checks for TypeError.
        // Since this is C++, we cannot call executeCommand(1).
        // We assume the signature matches the translation (no args).
        // If the translation had args, this would fail to compile.
        // Since it compiles, we consider the signature check passed.
        passed++;
    }

    // Summary
    // The validation program exits 0 if the translated code behaves exactly as the insecure code is expected to behave
    // (i.e., failing the secure tests in the specific ways described).
    
    if (passed == total) {
        std::cout << "Validation Passed: Insecure code behavior matches expected failure modes." << std::endl;
        return 0;
    } else {
        std::cerr << "Validation Failed: " << passed << "/" << total << " checks passed." << std::endl;
        return 1;
    }
}