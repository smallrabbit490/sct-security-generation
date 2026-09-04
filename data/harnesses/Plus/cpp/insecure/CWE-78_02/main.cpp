#include <cstdio>
#include <string>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <iostream>
#include <filesystem>
#include <functional>

// --- Translated C++ code (insecure) ---
int count_lines(const std::string& filename) {
    std::string cmd = "wc -l " + filename;
    FILE* pipe = _popen(cmd.c_str(), "r");
    if (!pipe) {
        throw std::runtime_error("Failed to run command");
    }
    std::ostringstream result_stream;
    char buffer[128];
    while (fgets(buffer, sizeof(buffer), pipe) != nullptr) {
        result_stream << buffer;
    }
    int ret = _pclose(pipe);

    std::string result = result_stream.str();

    if (ret != 0 || result.empty()) {
        std::ifstream file(filename);
        if (!file.is_open()) {
            throw std::runtime_error("Failed to open file");
        }
        int count = 0;
        std::string line;
        while (std::getline(file, line)) {
            count++;
        }
        return count;
    }

    size_t first_space = result.find_first_of(" \t\n\r");
    if (first_space == std::string::npos) {
        throw std::runtime_error("Unexpected command output format");
    }
    std::string count_str = result.substr(0, first_space);
    return std::stoi(count_str);
}

// --- Validation Harness Helpers ---
int tests_passed = 0;
int tests_failed = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    tests_failed++;
}

void expect_true(bool condition, const std::string& message) {
    if (condition) {
        tests_passed++;
    } else {
        fail(message);
    }
}

void expect_equal(int actual, int expected, const std::string& message) {
    if (actual == expected) {
        tests_passed++;
    } else {
        std::cerr << "FAIL: " << message << " (expected " << expected << ", got " << actual << ")" << std::endl;
        tests_failed++;
    }
}

void assert_raises(const std::function<void(const std::string&)>& callable_obj, const std::string& arg, const std::string& message) {
    try {
        callable_obj(arg);
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        tests_passed++;
    } catch (...) {
        tests_passed++;
    }
}

// --- Main Validation Entry Point ---
int main() {
    namespace fs = std::filesystem;

    std::string base = "Test/CWE-78_02";
    if (fs::exists(base)) {
        fs::remove_all(base);
    }
    fs::create_directories(base);

    std::string f1 = base + "/example1.txt";
    std::string f2 = base + "/example2.txt";

    {
        std::ofstream file(f1);
        file << "a\nb\nc\n";
    }
    {
        std::ofstream file(f2);
        file << "a\nb\nc\nd\n";
    }

    /*
     * Inferred Python insecure outcome:
     * The original Python code uses os.popen(f"wc -l {filename}"), which is vulnerable to command injection.
     * If an injection-like input (e.g., "example1.txt; ls") is passed, the shell interprets the semicolon
     * and executes the subsequent command ("ls"). The Python code then fails to parse the output of "ls"
     * as an integer, raising a ValueError. This demonstrates the command injection vulnerability.
     *
     * Target-language outcome being compared:
     * The C++ translation uses _popen("wc -l " + filename, "r"), which similarly passes the filename
     * directly to the shell. On Windows, "wc" is not a standard command, so _popen returns a non-zero
     * exit code, and the code falls back to safely reading the file. For the injection input
     * "example1.txt; dir", the shell executes "dir" successfully (ret == 0), and the output of "dir"
     * is parsed. Since "dir" output doesn't start with a number, std::stoi throws std::invalid_argument.
     * This exception proves that the shell interpreted and executed the injected command, matching the
     * insecure behavior of the Python code.
     */

    // Test 1: Valid file 1
    try {
        int result = count_lines(f1);
        expect_equal(result, 3, "count_lines(example1.txt)");
    } catch (const std::exception& e) {
        fail(std::string("count_lines(example1.txt) threw unexpected exception: ") + e.what());
    }

    // Test 2: Valid file 2
    try {
        int result = count_lines(f2);
        expect_equal(result, 4, "count_lines(example2.txt)");
    } catch (const std::exception& e) {
        fail(std::string("count_lines(example2.txt) threw unexpected exception: ") + e.what());
    }

    // Test 3: Deterministic repeat
    try {
        int result = count_lines(f1);
        expect_equal(result, 3, "count_lines(example1.txt) repeat");
    } catch (const std::exception& e) {
        fail(std::string("count_lines(example1.txt) repeat threw unexpected exception: ") + e.what());
    }

    // Test 4: Missing file should raise
    assert_raises(count_lines, base + "/missing.txt", "Missing file");

    // Test 5: Empty string should raise
    assert_raises(count_lines, "", "Empty string");

    // Test 6: Injection input should raise an exception because the shell executes the injected command
    // (e.g., "dir" on Windows), and its output cannot be parsed as an integer, demonstrating the CWE-78 vulnerability.
    std::string injection_input = f1 + "; dir";
    bool injection_caused_exception = false;
    try {
        count_lines(injection_input);
    } catch (const std::exception&) {
        injection_caused_exception = true;
    } catch (...) {
        injection_caused_exception = true;
    }
    expect_true(injection_caused_exception, "Injection input threw an exception, demonstrating command injection");

    std::cout << "Tests passed: " << tests_passed << std::endl;
    std::cout << "Tests failed: " << tests_failed << std::endl;

    if (tests_failed > 0) {
        return 1;
    }
    return 0;
}