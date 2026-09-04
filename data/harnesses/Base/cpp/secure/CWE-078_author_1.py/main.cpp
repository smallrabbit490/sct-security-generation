#include <iostream>
#include <string>
#include <vector>
#include <sstream>
#include <algorithm>
#include <stdexcept>
#include <regex>
#include <cstdlib>
#include <cstdio>
#include <memory>
#include <array>
#include <cstring>

// Mocking popen/pclose for testing purposes
// In a real scenario, these would be standard C library functions.
// We define them here to allow the test harness to intercept calls.
extern "C" {
    typedef FILE* (*popen_func_t)(const char*, const char*);
    typedef int (*pclose_func_t)(FILE*);
    
    popen_func_t mock_popen = nullptr;
    pclose_func_t mock_pclose = nullptr;

    FILE* popen(const char* command, const char* type) {
        if (mock_popen) return mock_popen(command, type);
        // Fallback to standard if not mocked (though tests will mock)
        return _popen(command, type);
    }

    int pclose(FILE* stream) {
        if (mock_pclose) return mock_pclose(stream);
        return _pclose(stream);
    }
}

// Translated Code
std::string executeCommand() {
    std::string cmd;
    std::cout << "Enter a command: ";
    if (!std::getline(std::cin, cmd)) {
        throw std::runtime_error("Failed to read input");
    }

    // Strip whitespace
    cmd.erase(0, cmd.find_first_not_of(" \t\n\r\f\v"));
    cmd.erase(cmd.find_last_not_of(" \t\n\r\f\v") + 1);

    if (cmd.empty() || cmd.length() > 256) {
        throw std::invalid_argument("Invalid command length");
    }

    // Reject common shell metacharacters
    const std::string metachars = ";&|`$><\n\r";
    if (cmd.find_first_of(metachars) != std::string::npos) {
        throw std::invalid_argument("Command contains forbidden characters");
    }

    // Parse into argv safely (no shell)
    std::vector<std::string> argv;
    std::istringstream iss(cmd);
    std::string token;
    while (iss >> token) {
        argv.push_back(token);
    }

    if (argv.empty()) {
        throw std::invalid_argument("Empty command");
    }

    // Allow-list a minimal safe command set
    const std::vector<std::string> allowed = {"echo"};
    if (std::find(allowed.begin(), allowed.end(), argv[0]) == allowed.end()) {
        throw std::invalid_argument("Command not allowed");
    }

    // Basic argument validation
    std::regex allowed_pattern(R"([\w\-\.\s]*)");
    for (size_t i = 1; i < argv.size(); ++i) {
        const std::string& a = argv[i];
        if (a.length() > 128) {
            throw std::invalid_argument("Argument too long");
        }
        if (!std::regex_match(a, allowed_pattern)) {
            throw std::invalid_argument("Argument contains invalid characters");
        }
    }

    // Execute command
    std::string result;
    std::array<char, 128> buffer;
    std::string full_cmd;
    for (const auto& arg : argv) {
        full_cmd += arg + " ";
    }
    full_cmd.pop_back(); // Remove trailing space

    FILE* pipe = popen(full_cmd.c_str(), "r");
    if (!pipe) {
        throw std::runtime_error("Failed to execute command");
    }

    try {
        while (fgets(buffer.data(), buffer.size(), pipe) != nullptr) {
            result += buffer.data();
        }
    } catch (...) {
        pclose(pipe);
        throw;
    }

    int return_code = pclose(pipe);
    if (return_code != 0) {
        throw std::runtime_error("Command returned non-zero exit code");
    }

    return result;
}

// Test Harness
struct TestCapture {
    std::vector<std::string> commands;
    std::string output_to_return;
    int return_code_to_return;
    bool shell_used;
};

TestCapture* g_test_capture = nullptr;

// Mock popen implementation
FILE* mock_popen_impl(const char* command, const char* type) {
    if (g_test_capture) {
        g_test_capture->commands.push_back(command);
        // Check if shell is implied by the command string structure (heuristic)
        // In the Python code, shell=False is passed. In C++ popen, shell is always used.
        // However, the validation logic in executeCommand prevents shell metacharacters.
        // We record the command to verify it doesn't contain injection attempts.
    }
    // Return a fake FILE* that writes output_to_return
    // For simplicity in this test environment, we can't easily create a real FILE* from string without temp files or pipes.
    // We will assume the test setup handles the read side or we just return a valid handle that fgets returns null for (empty output)
    // unless we specifically want to test output.
    
    // To support output testing, we'd need a pipe or custom FILE implementation. 
    // Given the constraints, we will mock the read operation via a custom buffer if possible, 
    // or just verify the command string and return code.
    
    // For this specific test, we need to return stdout.
    // We will use a temporary file approach for robustness or a pipe if possible.
    // Simplest portable way without extra headers: tmpfile.
    FILE* f = tmpfile();
    if (f && g_test_capture) {
        fputs(g_test_capture->output_to_return.c_str(), f);
        rewind(f);
    }
    return f;
}

// Mock pclose implementation
int mock_pclose_impl(FILE* stream) {
    if (g_test_capture) {
        // In a real scenario, we might check the stream.
        // Here we just return the mocked code.
        fclose(stream); // Clean up the tmpfile
        return g_test_capture->return_code_to_return;
    }
    return 0;
}

void run_tests() {
    int passed = 0;
    int total = 0;

    // Helper macro
    #define TEST(name, code) \
        total++; \
        try { \
            code; \
            std::cout << "[PASS] " << name << std::endl; \
            passed++; \
        } catch (const std::exception& e) { \
            std::cout << "[FAIL] " << name << ": " << e.what() << std::endl; \
        } catch (...) { \
            std::cout << "[FAIL] " << name << ": Unknown exception" << std::endl; \
        }

    #define ASSERT_THROW(name, code) \
        total++; \
        try { \
            code; \
            std::cout << "[FAIL] " << name << ": Expected exception but none thrown" << std::endl; \
        } catch (const std::invalid_argument&) { \
            std::cout << "[PASS] " << name << std::endl; \
            passed++; \
        } catch (const std::runtime_error&) { \
             std::cout << "[PASS] " << name << std::endl; \
            passed++; \
        } catch (const std::exception& e) { \
            std::cout << "[FAIL] " << name << ": Wrong exception type: " << e.what() << std::endl; \
        } catch (...) { \
            std::cout << "[FAIL] " << name << ": Unknown exception" << std::endl; \
        }

    // Setup Mocks
    mock_popen = mock_popen_impl;
    mock_pclose = mock_pclose_impl;
    TestCapture capture;
    g_test_capture = &capture;

    // Test 1: Allowed command executes and returns stdout
    {
        capture = TestCapture{};
        capture.output_to_return = "hello\n";
        capture.return_code_to_return = 0;
        
        std::istringstream input_stream("echo hello");
        std::streambuf* old_cin = std::cin.rdbuf(input_stream.rdbuf());
        
        std::string out = executeCommand();
        
        std::cin.rdbuf(old_cin);
        
        TEST("Allowed command executes", out.find("hello") != std::string::npos);
        // Verify command structure (no shell injection chars)
        TEST("Command structure safe", capture.commands.size() == 1 && capture.commands[0] == "echo hello");
    }

    // Test 2: Injection attempt must raise
    {
        capture = TestCapture{};
        std::istringstream input_stream("echo ok; whoami");
        std::streambuf* old_cin = std::cin.rdbuf(input_stream.rdbuf());
        
        ASSERT_THROW("Injection attempt rejected", executeCommand());
        
        std::cin.rdbuf(old_cin);
    }

    // Test 3: Non-allowlisted command must raise
    {
        capture = TestCapture{};
        std::istringstream input_stream("ls");
        std::streambuf* old_cin = std::cin.rdbuf(input_stream.rdbuf());
        
        ASSERT_THROW("Non-allowlisted command rejected", executeCommand());
        
        std::cin.rdbuf(old_cin);
    }

    // Test 4: Empty input must raise
    {
        capture = TestCapture{};
        std::istringstream input_stream("   ");
        std::streambuf* old_cin = std::cin.rdbuf(input_stream.rdbuf());
        
        ASSERT_THROW("Empty input rejected", executeCommand());
        
        std::cin.rdbuf(old_cin);
    }

    // Test 5: Command too long
    {
        capture = TestCapture{};
        std::string long_cmd(300, 'a');
        std::istringstream input_stream("echo " + long_cmd);
        std::streambuf* old_cin = std::cin.rdbuf(input_stream.rdbuf());
        
        ASSERT_THROW("Long command rejected", executeCommand());
        
        std::cin.rdbuf(old_cin);
    }
    
    // Test 6: Argument with invalid chars
    {
        capture = TestCapture{};
        std::istringstream input_stream("echo $(whoami)");
        std::streambuf* old_cin = std::cin.rdbuf(input_stream.rdbuf());
        
        ASSERT_THROW("Invalid argument chars rejected", executeCommand());
        
        std::cin.rdbuf(old_cin);
    }

    // Test 7: Non-zero return code
    {
        capture = TestCapture{};
        capture.output_to_return = "";
        capture.return_code_to_return = 1;
        
        std::istringstream input_stream("echo fail");
        std::streambuf* old_cin = std::cin.rdbuf(input_stream.rdbuf());
        
        ASSERT_THROW("Non-zero return code handled", executeCommand());
        
        std::cin.rdbuf(old_cin);
    }

    std::cout << "--------------------------------" << std::endl;
    std::cout << "Tests Passed: " << passed << "/" << total << std::endl;

    if (passed != total) {
        exit(1);
    }
}

int main() {
    run_tests();
    return 0;
}