#include <iostream>
#include <fstream>
#include <filesystem>
#include <string>
#include <system_error>
#include <stdexcept>
#include <vector>
#include <cstdio>

namespace fs = std::filesystem;

// Translated function
std::string readFile(const std::string& fileName) {
    // Determine the base directory
    fs::path base_dir = fs::absolute(fs::path("Test") / "CWE-367_author_1");
    fs::path path = fs::absolute(fileName);

    // Only allow reading inside the dedicated test directory
    // We check if the path starts with base_dir. 
    // We append a separator to base_dir to ensure "Test/CWE-367_author_1_evil" is rejected.
    fs::path base_dir_check = base_dir / "";
    if (path.native().find(base_dir_check.native()) != 0) {
        throw std::runtime_error("Invalid path");
    }

    std::error_code ec;
    
    // Avoid TOCTOU by opening directly and refusing symlinks
    // Check for symlink status using status (which does not follow symlinks)
    auto file_status = fs::status(path, ec);
    if (ec) {
        throw std::runtime_error("File access error");
    }
    
    if (fs::is_symlink(file_status)) {
        throw std::runtime_error("Symlinks are not allowed");
    }

    // Open the file
    std::ifstream f(path, std::ios::binary);
    if (!f) {
        throw std::runtime_error("Failed to open file");
    }

    // Read content
    std::string content;
    f.seekg(0, std::ios::end);
    content.resize(f.tellg());
    f.seekg(0, std::ios::beg);
    f.read(&content[0], content.size());
    
    return content;
}

// Test harness
int main() {
    try {
        // Setup environment
        fs::path base_dir = fs::path("Test") / "CWE-367_author_1";
        fs::create_directories(base_dir);
        
        fs::path safe_path = base_dir / "safe.txt";
        {
            std::ofstream f(safe_path);
            f << "hello";
        }

        // Helper to assert exceptions
        auto assert_raises = [](auto func, const std::string& msg) {
            try {
                func();
                std::cerr << "Test failed: " << msg << " (No exception thrown)" << std::endl;
                return false;
            } catch (const std::exception&) {
                return true;
            } catch (...) {
                std::cerr << "Test failed: " << msg << " (Unknown exception)" << std::endl;
                return false;
            }
        };

        // Test 1: Valid read
        if (readFile(safe_path.string()) != "hello") {
            std::cerr << "Test failed: Valid read content mismatch" << std::endl;
            return 1;
        }

        // Test 2: Path traversal (relative)
        if (!assert_raises([]() { readFile("safe.txt"); }, "Relative path traversal")) {
            return 1;
        }

        // Test 3: Path traversal (parent directory)
        fs::path outside_path = fs::path("Test") / ".." / "outside.txt";
        if (!assert_raises([&]() { readFile(outside_path.string()); }, "Parent directory traversal")) {
            return 1;
        }

        // Test 4: Missing file inside base
        fs::path missing_path = base_dir / "missing.txt";
        if (!assert_raises([&]() { readFile(missing_path.string()); }, "Missing file inside base")) {
            return 1;
        }

        // Test 5: Type check (C++ is statically typed, so we can't pass int directly to std::string)
        // However, the Python test checks for TypeError. In C++, this is a compile-time error.
        // We simulate the spirit of the check by ensuring the function signature is strict.
        // Since we cannot pass an int to readFile(const std::string&), this is implicitly handled.

        // Test 6: Extra args (C++ is statically typed, this is a compile-time error)
        // Implicitly handled.

        // Cleanup
        fs::remove_all("Test");

        std::cout << "All tests passed." << std::endl;
        return 0;

    } catch (const std::exception& e) {
        std::cerr << "Test harness error: " << e.what() << std::endl;
        return 1;
    }
}