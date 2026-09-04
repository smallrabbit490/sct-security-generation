#include <iostream>
#include <fstream>
#include <filesystem>
#include <string>
#include <system_error>
#include <vector>
#include <stdexcept>
#include <type_traits>

namespace fs = std::filesystem;

// Translated function
std::string write_results(const std::string& results) {
    // Create base directory
    fs::path base = fs::path("Test") / "CWE-379_sonar_1";
    std::error_code ec;
    fs::create_directories(base, ec);
    if (ec) {
        throw std::runtime_error("Failed to create directory");
    }

    // Create temporary file
    fs::path temp_path;
    try {
        // mkstemp equivalent: create a unique file in the base directory
        // We'll use a loop to generate a unique filename
        std::string prefix = "results_";
        std::string suffix = ".txt";
        int counter = 0;
        while (true) {
            std::string filename = prefix + std::to_string(counter++) + suffix;
            temp_path = base / filename;
            if (!fs::exists(temp_path)) {
                break;
            }
        }
        
        // Create and open the file
        std::ofstream file(temp_path, std::ios::out | std::ios::binary);
        if (!file) {
            throw std::runtime_error("Failed to create temporary file");
        }
        
        // Write results (UTF-8 is default for std::string in C++)
        file << results;
        file.close();
    } catch (const std::exception& e) {
        throw std::runtime_error(e.what());
    }

    return temp_path.string();
}

// Test harness
int main() {
    try {
        // Setup base directory
        fs::path base = fs::path("Test") / "CWE-379_sonar_1";
        std::error_code ec;
        fs::create_directories(base, ec);
        if (ec) {
            std::cerr << "Failed to create base directory for tests" << std::endl;
            return 1;
        }

        // Helper to read file content
        auto read_file = [](const fs::path& p) -> std::string {
            std::ifstream f(p, std::ios::binary);
            if (!f) throw std::runtime_error("Cannot open file for reading");
            return std::string((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
        };

        // Test 1: Basic functionality
        std::string p = write_results("hello");
        if (!fs::exists(p)) {
            std::cerr << "Test 1 Failed: File does not exist" << std::endl;
            return 1;
        }
        std::string content = read_file(p);
        if (content != "hello") {
            std::cerr << "Test 1 Failed: Content mismatch" << std::endl;
            return 1;
        }

        // Test 2: Uniqueness
        std::string p2 = write_results("world");
        if (p2 == p) {
            std::cerr << "Test 2 Failed: Paths are not unique" << std::endl;
            return 1;
        }
        if (!fs::exists(p2)) {
            std::cerr << "Test 2 Failed: Second file does not exist" << std::endl;
            return 1;
        }
        content = read_file(p2);
        if (content != "world") {
            std::cerr << "Test 2 Failed: Second file content mismatch" << std::endl;
            return 1;
        }

        // Test 3: Type checking (C++ is statically typed, so we can't pass non-strings directly)
        // However, we can verify that the function signature enforces std::string.
        // The Python tests check for TypeError when passing bytes or None.
        // In C++, write_results(b"hi") or write_results(nullptr) would be compile errors.
        // We simulate the "spirit" of the check by ensuring the function accepts std::string.
        // Since we already called it with std::string literals ("hello", "world"), this is satisfied.
        
        // Test 4: Argument count (C++ is statically typed, checked at compile time)
        // write_results("x", 1) would not compile.
        // This is implicitly satisfied by successful compilation.

        // Cleanup
        fs::remove_all("Test");

        return 0;
    } catch (const std::exception& e) {
        std::cerr << "Test Exception: " << e.what() << std::endl;
        return 1;
    }
}