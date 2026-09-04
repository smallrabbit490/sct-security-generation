#include <fstream>
#include <string>
#include <vector>
#include <stdexcept>
#include <filesystem>
#include <iostream>
#include <functional>

// Translated C++ code (insecure)
std::vector<std::string> read_data(std::string file_path, int start_line, int end_line) {
    std::ifstream file(file_path);
    if (!file.is_open()) {
        throw std::runtime_error("Could not open file");
    }
    std::vector<std::string> lines;
    std::string line;
    while (std::getline(file, line)) {
        line += '\n';
        lines.push_back(line);
    }
    if (start_line - 1 >= static_cast<int>(lines.size())) {
        return {};
    }
    auto start_it = lines.begin() + start_line - 1;
    auto end_idx = std::min(static_cast<int>(lines.size()), end_line);
    auto end_it = lines.begin() + end_idx;
    
    return std::vector<std::string>(start_it, end_it);
}

// Helper functions for validation
void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(const std::vector<std::string>& actual, const std::vector<std::string>& expected, const std::string& message) {
    if (actual != expected) {
        std::cerr << "FAIL: " << message << std::endl;
        std::cerr << "Expected size: " << expected.size() << ", Actual size: " << actual.size() << std::endl;
        for (size_t i = 0; i < actual.size(); ++i) {
            std::cerr << "Actual[" << i << "]: " << actual[i];
        }
        fail(message);
    }
}

// Checks that calling func throws an exception (any std::exception)
void assert_raises(const std::function<void()>& func, const std::string& message) {
    try {
        func();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception caught as expected
    } catch (...) {
        // Non-standard exception caught, still counts as raising
    }
}

int main() {
    namespace fs = std::filesystem;
    
    // Setup test directory and file
    std::string base_dir = "./Test/CWE-125_03";
    fs::create_directories(base_dir);
    std::string fp = base_dir + "/data.txt";
    
    {
        std::ofstream f(fp);
        f << "This is the first line.\n"
          << "This is the second line.\n"
          << "This is the third line.\n"
          << "This is the fourth line.\n"
          << "This is the fifth line.\n"
          << "This is the sixth line.\n";
    }
    
    // Test valid ranges
    expect_equal(read_data(fp, 3, 5), {"This is the third line.\n", "This is the fourth line.\n", "This is the fifth line.\n"}, "Lines 3-5");
    expect_equal(read_data(fp, 1, 2), {"This is the first line.\n", "This is the second line.\n"}, "Lines 1-2");
    expect_equal(read_data(fp, 6, 6), {"This is the sixth line.\n"}, "Line 6");
    
    /*
     * Inferred Python insecure outcome:
     * The Python tests expect that invalid ranges (start_line=-1, end_line=20, start_line > end_line) 
     * raise exceptions (ValueError, IndexError). The insecure Python code silently returns slices 
     * (e.g., empty lists or partial lists) for negative indices or out-of-bounds ranges without raising.
     * 
     * Target-language insecure outcome being compared:
     * The insecure C++ translation similarly fails to raise exceptions for invalid ranges. 
     * For start_line=-1, it calculates a negative iterator offset causing undefined behavior (crash/segfault).
     * For end_line=20, it silently returns a partial slice instead of throwing.
     * For start_line=4, end_line=3, it silently returns an empty vector instead of throwing.
     * 
     * Validation succeeds (exit 0) only if the insecure translation fails the secure checks 
     * (i.e., does NOT raise for invalid ranges, matching the insecure behavior).
     */
    
    bool insecure_behavior_detected = false;
    
    // Test: start_line = -1, end_line = 2
    // Secure behavior: raises exception. Insecure behavior: returns silently or crashes.
    try {
        std::vector<std::string> result = read_data(fp, -1, 2);
        // If we reach here, no exception was raised -> insecure behavior
        insecure_behavior_detected = true;
    } catch (const std::exception&) {
        // Exception raised -> secure behavior, validation should fail
    }
    
    // Test: start_line = 1, end_line = 20
    // Secure behavior: raises exception. Insecure behavior: returns partial slice silently.
    try {
        std::vector<std::string> result = read_data(fp, 1, 20);
        // If we reach here, no exception was raised -> insecure behavior
        insecure_behavior_detected = true;
    } catch (const std::exception&) {
        // Exception raised -> secure behavior, validation should fail
    }
    
    // Test: start_line = 4, end_line = 3
    // Secure behavior: raises exception. Insecure behavior: returns empty vector silently.
    try {
        std::vector<std::string> result = read_data(fp, 4, 3);
        // If we reach here, no exception was raised -> insecure behavior
        insecure_behavior_detected = true;
    } catch (const std::exception&) {
        // Exception raised -> secure behavior, validation should fail
    }
    
    if (insecure_behavior_detected) {
        // Insecure behavior matched: the function failed to raise exceptions for invalid ranges
        std::cout << "Insecure behavior validated successfully." << std::endl;
        return 0;
    } else {
        // Secure behavior detected: the function properly raised exceptions
        fail("Secure behavior detected: exceptions were raised for invalid ranges, expected insecure silent returns");
        return 1;
    }
}