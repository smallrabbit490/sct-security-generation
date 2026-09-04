#include <cstdio>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>

namespace fs = std::filesystem;

// --- Translated C++ Code ---
std::string process_input_file(const std::string& filename) {
    std::string cmd = "cat " + filename;
    FILE* pipe = popen(cmd.c_str(), "r");
    if (!pipe) {
        throw std::runtime_error("Failed to execute command");
    }
    char buffer[128];
    while (fgets(buffer, sizeof(buffer), pipe) != nullptr) {
        // Read output to simulate os.popen().read()
    }
    pclose(pipe);
    return "Processed data from " + filename;
}

// --- Validation Helpers ---
void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " - Expected: '" + expected + "', Got: '" + actual + "'");
    }
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

// --- Main Validation Entry Point ---
int main() {
    /*
     * Inferred Python insecure outcome:
     * The Python code uses os.popen(f"cat {filename}") which is vulnerable to 
     * OS Command Injection (CWE-78). When a malicious filename like 
     * "data1.txt; pwd" is passed, the shell executes both "cat data1.txt" and "pwd".
     * The Python tests expect this to raise an exception (FileNotFoundError, ValueError, 
     * or RuntimeError) for such inputs. However, the insecure Python code does NOT 
     * raise an exception; it successfully executes the injected command and returns 
     * "Processed data from data1.txt; pwd". Thus, the insecure behavior is that the 
     * function accepts the malicious input without raising an exception.
     *
     * Target-language insecure outcome being compared:
     * The C++ translation uses popen(("cat " + filename).c_str(), "r"), which similarly 
     * passes the concatenated string to the shell, making it vulnerable to command injection.
     * For the malicious filename "data1.txt; pwd", popen will successfully execute the 
     * injected command, return a valid pipe, and the function will return the string 
     * "Processed data from data1.txt; pwd" without throwing any exception.
     * 
     * Validation check:
     * If the C++ code is insecure (matches the Python behavior), it will NOT throw an 
     * exception for the malicious input, and we exit 0. If the C++ code is fixed (e.g., 
     * by validating the filename or using execvp instead of popen), it will throw an 
     * exception, and we must exit non-zero.
     */

    fs::path base = fs::current_path() / "Test" / "CWE-78_03";
    fs::remove_all(base);
    fs::create_directories(base);

    fs::path d1 = base / "data1.txt";
    fs::path d2 = base / "data2.txt";

    {
        std::ofstream f(d1);
        f << "hello\n";
    }
    {
        std::ofstream f(d2);
        f << "world\n";
    }

    // Test normal inputs
    std::string res1 = process_input_file(d1.string());
    expect_equal(res1, "Processed data from " + d1.string(), "Normal input d1");

    std::string res2 = process_input_file(d2.string());
    expect_equal(res2, "Processed data from " + d2.string(), "Normal input d2");

    // Test malicious input (Command Injection)
    std::string malicious_filename = d1.string() + "; pwd";
    bool exception_thrown = false;
    try {
        std::string res_malicious = process_input_file(malicious_filename);
        // If no exception is thrown, the command injection was successful (insecure behavior).
        // We verify it returned the concatenated string just like the insecure Python code.
        expect_equal(res_malicious, "Processed data from " + malicious_filename, "Malicious input result");
    } catch (const std::exception& e) {
        // An exception was thrown, meaning the vulnerability was likely fixed (secure behavior).
        exception_thrown = true;
    }

    if (exception_thrown) {
        fail("An exception was raised for the malicious input, indicating the vulnerability is fixed. Expected insecure behavior (no exception).");
    }

    fs::remove_all(base);

    return 0;
}