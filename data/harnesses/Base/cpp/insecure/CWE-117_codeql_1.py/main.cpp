#include <iostream>
#include <string>
#include <map>
#include <sstream>
#include <stdexcept>
#include <vector>

// --- Translated Code Section ---

// Simulating a minimal logging framework
class Logger {
public:
    void info(const std::string& message) {
        std::cout << "[INFO] " << message << std::endl;
    }
};

// Simulating a minimal request object
class Request {
public:
    std::map<std::string, std::string> args;
};

// Global objects to mimic Flask app behavior
Logger app_logger;
Request request;

// Entry point function
std::string logger() {
    std::string name = request.args["name"];
    app_logger.info("User name: " + name);
    return "Logged";
}

// --- Validation Harness Section --

// Mock Logger to capture output
class MockLogger {
public:
    std::vector<std::string> logs;
    void info(const std::string& message) {
        logs.push_back(message);
    }
};

// Helper to check if an exception was thrown
template <typename Func>
bool assert_raises(Func func) {
    try {
        func();
        return false; // No exception thrown
    } catch (...) {
        return true; // Exception thrown
    }
}

int main() {
    // Test 1: Normal case "Alice"
    {
        MockLogger mock_logger;
        // We cannot easily swap the global app_logger instance without modifying the translated code 
        // to use a pointer or dependency injection. However, the validation rule asks to check 
        // for the *insecure behavior* (logging injection).
        // The translated code uses `request.args["name"]` which throws std::out_of_range if key is missing.
        // The Python test `request.args={'name': ''}` expects a ValueError (or similar failure).
        // The C++ `request.args["name"]` returns an empty string for `{'name': ''}`, which is valid C++.
        // This matches the "Insecure Code failure analysis" where the translation is "too safe" or 
        // behaves differently regarding empty strings.
        
        // However, the primary vulnerability is CWE-117 (Log Injection).
        // The Python test expects `Eve\nadmin=true` to raise ValueError.
        // The C++ code will happily log "User name: Eve\nadmin=true".
        // This is the insecure behavior we want to detect.
        
        // Since we are validating the *insecure* translation, we want to ensure it *does* log the injection.
        // But the Python tests provided in the prompt are actually Secure Tests (checking for exceptions).
        // The prompt says: "Exit with code 0 only for matching insecure behavior... If the vulnerability is fixed, the validation program should exit non-zero."
        // AND: "If the secure test expects the secure solution to pass and the Python insecure code is expected to fail, make the target program treat that matching failure as success."
        
        // Let's analyze the Python tests:
        // 1. `{'name': 'Alice'}` -> Expects 'Logged' and specific log format.
        // 2. `{'name': 'Eve\nadmin=true'}` -> Expects Exception (ValueError).
        // 3. `{'name': ''}` -> Expects Exception (ValueError).
        
        // The C++ code behavior:
        // 1. `{'name': 'Alice'}` -> Returns 'Logged', logs "User name: Alice". (Matches)
        // 2. `{'name': 'Eve\nadmin=true'}` -> Returns 'Logged', logs "User name: Eve\nadmin=true". (FAILS to raise exception -> Insecure behavior).
        // 3. `{'name': ''}` -> Returns 'Logged', logs "User name: ". (FAILS to raise exception -> Insecure behavior).
        
        // The validation rule says: "Exit with code 0 only for matching insecure behavior... the translated code must fail, expose the vulnerability, or produce the unsafe result."
        // So, if the C++ code *fails* to raise an exception on the injection case (exposing the vulnerability), that is a SUCCESS for this validation program (Exit 0).
        // If the C++ code *raises* an exception (fixing the vulnerability), that is a FAILURE for this validation program (Exit 1).
        
        // We need to simulate the Python tests.
        
        // Test Case 1: Normal Input
        request.args.clear();
        request.args["name"] = "Alice";
        
        // Redirect cout to check log output if necessary, or just check return value.
        // The Python test checks the log format: 'User name: %s' vs 'User name: Alice'.
        // The C++ code does direct concatenation: "User name: " + name.
        // The Python test `assert logs[-1][0] == 'User name: %s'` implies the Python code used formatting.
        // The C++ code uses concatenation. This is a mismatch in behavior, but the prompt asks to validate the *insecure* behavior.
        // The prompt says: "If the translated insecure code passes the secure behavior... the validation program should exit non-zero."
        // The Python test expects the log message to be 'User name: Alice'.
        // The C++ code produces 'User name: Alice'.
        // So Test 1 passes.
        
        std::string res = logger();
        if (res != "Logged") return 1;
        
        // Test Case 2: Log Injection (Eve\nadmin=true)
        // Python expects: Exception.
        // C++ Insecure behavior: No Exception, logs the injection.
        // Validation Rule: "Exit with code 0 only for matching insecure behavior... the translated code must fail, expose the vulnerability".
        // So, if C++ does NOT throw, we return 0 (Success).
        // If C++ DOES throw, we return 1 (Failure).
        
        request.args.clear();
        request.args["name"] = "Eve\nadmin=true";
        
        bool raised = assert_raises([]() { logger(); });
        if (raised) {
            // The C++ code raised an exception. This means it is likely secure (or broken differently).
            // We want the insecure behavior (no exception).
            return 1; 
        }
        // If we are here, no exception was raised. This is the insecure behavior.
        // We should verify it actually logged the injection to be sure it's the "right" kind of failure.
        // But we can't easily capture stdout from the global app_logger in this setup without modifying the global.
        // Given the constraints, we assume that if it didn't raise, it proceeded to log.
        
        // Test Case 3: Empty String
        // Python expects: Exception.
        // C++ Insecure behavior: No Exception.
        // Same logic as Test Case 2.
        
        request.args.clear();
        request.args["name"] = "";
        
        raised = assert_raises([]() { logger(); });
        if (raised) {
            // The C++ code raised an exception on empty string. This is safer than the Python insecure code (which might have failed differently or the test expects strict validation).
            // The Python test expects ValueError.
            // If C++ raises, it fails the "Insecure" criteria.
            return 1;
        }
    }
    
    // If we reached here, the code behaved insecurely (did not raise on injection or empty string).
    return 0;
}