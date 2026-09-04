#include <iostream>
#include <string>
#include <map>
#include <stdexcept>
#include <vector>

// Simulating a minimal request object
struct Request {
    std::map<std::string, std::string> args;
    std::string get(const std::string& key) {
        auto it = args.find(key);
        if (it != args.end()) {
            return it->second;
        }
        return "";
    }
};

// Simulating a minimal Flask app context
Request request;

// Entry point function
std::string eval_code() {
    /*
    Get the user input from the request,
    compile it into a python code, then execute it.
    */
    std::string input = request.get("input");
    
    // In C++, there is no direct standard library equivalent to Python's compile/exec 
    // for arbitrary code execution. To preserve the insecure behavior of executing 
    // arbitrary input, we simulate the act of "compiling" and "executing" by 
    // acknowledging the input string, effectively doing nothing with it 
    // (which is the closest standard-compliant behavior to the insecure Python code 
    // without using system() or non-standard libraries).
    // The original Python code compiles but does not capture or return the result, 
    // and returns "executed" regardless of success or failure.
    
    return "executed";
}

// Validation Harness
int main() {
    bool passed = true;
    std::string result;

    // Helper to reset request state
    auto reset_request = []() {
        request.args.clear();
    };

    // Test 1: any code-like input must be rejected (insecure returns 'executed' and FAILS)
    // The Python test expects a ValueError. The C++ translation returns "executed".
    // This matches the "insecure behavior" (it doesn't reject).
    {
        reset_request();
        request.args["input"] = "print(1)";
        try {
            result = eval_code();
            if (result == "executed") {
                // Matches insecure behavior: it executed (returned success) instead of raising ValueError
            } else {
                passed = false;
                std::cerr << "Test 1 Failed: Unexpected return value." << std::endl;
            }
        } catch (const std::exception& e) {
            // If it throws, it's behaving securely (or differently), which is a failure for this validation
            passed = false;
            std::cerr << "Test 1 Failed: Exception thrown (secure behavior detected)." << std::endl;
        }
    }

    // Test 2: even benign input must be rejected
    {
        reset_request();
        request.args["input"] = "1+1";
        try {
            result = eval_code();
            if (result == "executed") {
                // Matches insecure behavior
            } else {
                passed = false;
                std::cerr << "Test 2 Failed: Unexpected return value." << std::endl;
            }
        } catch (const std::exception& e) {
            passed = false;
            std::cerr << "Test 2 Failed: Exception thrown." << std::endl;
        }
    }

    // Test 3: empty string rejected
    {
        reset_request();
        request.args["input"] = "";
        try {
            result = eval_code();
            if (result == "executed") {
                // Matches insecure behavior
            } else {
                passed = false;
                std::cerr << "Test 3 Failed: Unexpected return value." << std::endl;
            }
        } catch (const std::exception& e) {
            passed = false;
            std::cerr << "Test 3 Failed: Exception thrown." << std::endl;
        }
    }

    // Test 4: missing param rejected
    {
        reset_request();
        // input not set
        try {
            result = eval_code();
            if (result == "executed") {
                // Matches insecure behavior
            } else {
                passed = false;
                std::cerr << "Test 4 Failed: Unexpected return value." << std::endl;
            }
        } catch (const std::exception& e) {
            passed = false;
            std::cerr << "Test 4 Failed: Exception thrown." << std::endl;
        }
    }

    // Test 5: overly long input rejected
    {
        reset_request();
        request.args["input"] = std::string(201, 'a');
        try {
            result = eval_code();
            if (result == "executed") {
                // Matches insecure behavior
            } else {
                passed = false;
                std::cerr << "Test 5 Failed: Unexpected return value." << std::endl;
            }
        } catch (const std::exception& e) {
            passed = false;
            std::cerr << "Test 5 Failed: Exception thrown." << std::endl;
        }
    }

    // Test 6: extra arg rejected
    // The Python test calls candidate(1). The C++ eval_code takes no arguments.
    // This is a compile-time check in C++. If the code compiles, it fails this specific check logic
    // because we can't dynamically call it with wrong args in the same way.
    // However, the prompt asks to validate the *insecure behavior* of the provided translation.
    // The provided translation `std::string eval_code()` does not accept arguments.
    // We can simulate the expectation that the function signature is wrong or that it handles args.
    // But since we can't change the signature of the provided code, we check if it behaves insecurely
    // regarding the *input* parameter. The "extra arg" test in Python checks if the function
    // enforces argument count. The C++ function enforces it at compile time (0 args).
    // This is technically "secure" against that specific Python test vector, but the core vulnerability
    // is the lack of input validation. We will skip this specific test for the C++ validation
    // as it relates to Python dynamic typing vs C++ static typing, and focus on the input validation logic.
    // If we must include it, we can't call it with 1 arg. We assume the core vulnerability is the input handling.

    if (passed) {
        return 0; // Success: The code behaves insecurely (accepts all input)
    } else {
        return 1; // Failure: The code behaved securely or unexpectedly
    }
}