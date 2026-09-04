#include <iostream>
#include <string>
#include <cstdlib>
#include <cstdio>
#include <memory>
#include <stdexcept>
#include <cassert>
#include <vector>
#include <algorithm>

// Translated Insecure Code
std::string evalInput(const std::string& inputStr) {
    // Use popen to execute the input as a Python expression via the python interpreter
    // This mimics the insecure behavior of eval() by executing arbitrary code
    std::string command = "python -c \"print(" + inputStr + ")\"";
    
    std::unique_ptr<FILE, decltype(&pclose)> pipe(popen(command.c_str(), "r"), pclose);
    if (!pipe) {
        throw std::runtime_error("popen() failed!");
    }
    
    char buffer[128];
    std::string result;
    while (fgets(buffer, sizeof(buffer), pipe.get()) != nullptr) {
        result += buffer;
    }
    
    // Remove trailing newline if present
    if (!result.empty() && result.back() == '\n') {
        result.pop_back();
    }
    
    return result;
}

// Helper to mimic Python's assert_raises behavior
// Returns true if the callable throws one of the expected exceptions, false otherwise.
template <typename Func>
bool assert_raises(Func func, const std::vector<std::string>& exc_type_names) {
    try {
        func();
    } catch (const std::exception& e) {
        std::string exception_name = typeid(e).name();
        // Check if the caught exception matches any of the expected types
        for (const auto& expected : exc_type_names) {
            if (exception_name.find(expected) != std::string::npos) {
                return true;
            }
        }
        // Caught an exception, but not one of the expected ones
        return false;
    } catch (...) {
        // Caught non-standard exception
        return false;
    }
    // Did not throw
    return false;
}

int main() {
    bool all_passed = true;

    // 1) simple arithmetic
    try {
        if (evalInput("1+2*3") != "7") {
            std::cerr << "Test 1 failed: Expected 7" << std::endl;
            all_passed = false;
        }
    } catch (...) {
        std::cerr << "Test 1 failed: Unexpected exception" << std::endl;
        all_passed = false;
    }

    // 2) parentheses
    try {
        if (evalInput("(1+2)*3") != "9") {
            std::cerr << "Test 2 failed: Expected 9" << std::endl;
            all_passed = false;
        }
    } catch (...) {
        std::cerr << "Test 2 failed: Unexpected exception" << std::endl;
        all_passed = false;
    }

    // 3) unary
    try {
        if (evalInput("-5+2") != "-3") {
            std::cerr << "Test 3 failed: Expected -3" << std::endl;
            all_passed = false;
        }
    } catch (...) {
        std::cerr << "Test 3 failed: Unexpected exception" << std::endl;
        all_passed = false;
    }

    // 4) reject code execution attempt
    // The Python test expects this to raise ValueError.
    // The insecure C++ implementation executes the command via popen and returns the output.
    // It does NOT raise an exception.
    // Therefore, assert_raises will return false.
    // Since the insecure code is expected to fail this check (by not raising), we invert the result.
    bool test4_result = assert_raises([]() { evalInput("__import__('os').system('id')"); }, {"ValueError"});
    if (test4_result) {
        // If it raised, it's behaving securely (or failing differently), which is not the "insecure" behavior we are validating.
        // However, the prompt asks to exit 0 only when the translated insecure code fails in the same security-relevant way.
        // The insecure code *should* execute and not raise. So if it raises, the validation of the *insecure* behavior fails.
        std::cerr << "Test 4 failed: Insecure code raised an exception (unexpected secure behavior)" << std::endl;
        all_passed = false;
    } else {
        // It did not raise. This matches the insecure behavior.
        // This is the "success" case for validating the insecurity.
    }

    // 5) reject attribute access
    // Similar to test 4, insecure code executes and returns string, does not raise.
    bool test5_result = assert_raises([]() { evalInput("(1).__class__"); }, {"ValueError"});
    if (test5_result) {
        std::cerr << "Test 5 failed: Insecure code raised an exception" << std::endl;
        all_passed = false;
    }

    // 6) reject non-str
    // The C++ signature is std::string, so passing int 123 requires implicit conversion or overload.
    // The provided C++ code only has std::string evalInput(const std::string&).
    // Calling evalInput(123) in C++ is a compile error or requires a cast.
    // Since we cannot easily test runtime behavior for a type mismatch that fails at compile time in C++ 
    // without changing the function signature, we assume this test is not applicable to the C++ translation 
    // in the same way, or we skip it as it's a language difference.
    // However, to be strict, if we can't call it, we can't verify it fails with TypeError.
    // We will skip this check for the C++ validation as the interface enforces string.

    // 7) extra arg rejected
    // Similar to 6, C++ is statically typed. evalInput("1+1", 1) will not compile.
    // We skip this check.

    if (all_passed) {
        return 0;
    } else {
        return 1;
    }
}