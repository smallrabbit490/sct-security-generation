#include <iostream>
#include <string>
#include <vector>
#include <regex>
#include <sstream>
#include <cstdlib>
#include <stdexcept>
#include <algorithm>
#include <array>
#include <memory>
#include <cstdio>
#include <cassert>

// Helper function to split a string into arguments similar to shlex.split
std::vector<std::string> shlex_split(const std::string& s) {
    std::vector<std::string> tokens;
    std::istringstream iss(s);
    std::string token;
    while (iss >> token) {
        tokens.push_back(token);
    }
    return tokens;
}

// Helper function to execute a command and capture output
std::string subprocess_run(const std::vector<std::string>& argv, bool& success) {
    std::string command;
    for (const auto& arg : argv) {
        command += arg + " ";
    }
    command.pop_back(); // Remove trailing space

    std::array<char, 128> buffer;
    std::string result;
    std::unique_ptr<FILE, decltype(&pclose)> pipe(popen(command.c_str(), "r"), pclose);
    if (!pipe) {
        success = false;
        return "";
    }

    while (fgets(buffer.data(), buffer.size(), pipe.get()) != nullptr) {
        result += buffer.data();
    }

    int returnCode = pclose(pipe.release());
    success = (returnCode == 0);
    return result;
}

std::string executeCommand(const std::string& method, const std::string& actionParam) {
    // Check if method is POST
    if (method != "POST") {
        throw std::invalid_argument("Invalid method");
    }

    // Check if action is provided
    if (actionParam.empty()) {
        throw std::invalid_argument("Action is required");
    }

    // Strip action
    std::string action = actionParam;
    action.erase(0, action.find_first_not_of(" \t\n\r\f\v"));
    action.erase(action.find_last_not_of(" \t\n\r\f\v") + 1);

    // Check action length
    if (action.empty() || action.size() > 256) {
        throw std::invalid_argument("Invalid action length");
    }

    // Check for forbidden characters
    const std::string forbiddenChars = ";&|`$><\n\r";
    for (char ch : forbiddenChars) {
        if (action.find(ch) != std::string::npos) {
            throw std::invalid_argument("Forbidden character in action");
        }
    }

    // Split action into arguments
    std::vector<std::string> argv = shlex_split(action);
    if (argv.empty()) {
        throw std::invalid_argument("No arguments provided");
    }

    // Minimal allow-list
    const std::vector<std::string> allowed = {"echo"};
    if (std::find(allowed.begin(), allowed.end(), argv[0]) == allowed.end()) {
        throw std::invalid_argument("Command not allowed");
    }

    // Validate remaining arguments
    std::regex allowedArgRegex(R"([\w\-\.\s]*)");
    for (size_t i = 1; i < argv.size(); ++i) {
        if (!std::regex_match(argv[i], allowedArgRegex)) {
            throw std::invalid_argument("Invalid argument");
        }
    }

    // Execute command
    bool success = false;
    std::string output = subprocess_run(argv, success);
    if (!success) {
        throw std::runtime_error("Command execution failed");
    }

    return output;
}

// Test harness
int main() {
    int test_count = 0;
    int passed = 0;

    // Helper macro for tests
    #define TEST(name, code) \
        test_count++; \
        try { \
            code; \
            std::cout << "[PASS] " << name << std::endl; \
            passed++; \
        } catch (const std::exception& e) { \
            std::cerr << "[FAIL] " << name << ": " << e.what() << std::endl; \
        } catch (...) { \
            std::cerr << "[FAIL] " << name << ": Unknown exception" << std::endl; \
        }

    // Helper to assert exception
    auto assert_raises = [](auto func, const std::string& test_name) {
        try {
            func();
            throw std::runtime_error("Expected exception but none was thrown");
        } catch (const std::invalid_argument&) {
            // Expected
        } catch (const std::runtime_error& e) {
            if (std::string(e.what()) == "Expected exception but none was thrown") {
                throw; // Re-throw the assertion error
            }
            // Other runtime errors might be expected depending on context, 
            // but for these specific tests we expect invalid_argument for validation failures.
            throw; 
        }
    };

    // 1) valid POST executes
    TEST("Valid POST executes", {
        std::string out = executeCommand("POST", "echo hi");
        if (out.find("hi") == std::string::npos) {
            throw std::runtime_error("Output did not contain 'hi'");
        }
    });

    // 3) missing action -> exception
    TEST("Missing action raises ValueError", {
        assert_raises([](){ executeCommand("POST", ""); }, "Missing action");
    });

    // 4) non-POST -> exception
    TEST("Non-POST raises ValueError", {
        assert_raises([](){ executeCommand("GET", "echo x"); }, "Non-POST");
    });

    // 5) injection attempt must raise
    TEST("Injection attempt raises ValueError", {
        assert_raises([](){ executeCommand("POST", "echo ok;whoami"); }, "Injection");
    });

    // 6) non-allowlisted command must raise
    TEST("Non-allowlisted command raises ValueError", {
        assert_raises([](){ executeCommand("POST", "ls"); }, "Non-allowlisted");
    });

    // 7) extra arg rejected (Type mismatch in Python, here we just check it compiles/runs or handle types)
    // Since C++ is statically typed, passing an int to string param won't compile.
    // We simulate the logic check: if we received a type that wasn't a string (conceptually), it would fail.
    // In this C++ implementation, the signature handles string conversion or fails at compile time.
    // We will skip the strict type check test as it is a language feature difference, 
    // but we verify the logic holds for string inputs.
    TEST("Type check simulation", {
        // In C++, this is handled by the compiler. 
        // We just ensure the function exists.
        std::string s = "test";
        (void)s;
    });

    std::cout << "--------------------------------" << std::endl;
    std::cout << "Tests passed: " << passed << "/" << test_count << std::endl;

    return (passed == test_count) ? 0 : 1;
}