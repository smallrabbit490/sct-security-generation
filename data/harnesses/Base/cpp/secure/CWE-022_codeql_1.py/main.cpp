#include <iostream>
#include <fstream>
#include <string>
#include <filesystem>
#include <stdexcept>
#include <vector>
#include <cassert>
#include <cstring>

namespace fs = std::filesystem;

// Translated function
std::vector<uint8_t> getFileData(const std::string& filename) {
    if (filename.empty() || filename.find('\x00') != std::string::npos) {
        throw std::invalid_argument("Invalid filename");
    }

    fs::path base_dir = fs::path("Test") / "CWE-022_codeql_1" / "files";
    fs::create_directories(base_dir);
    
    // Resolve base_dir to an absolute path. 
    // If it doesn't exist yet, use absolute() instead of canonical() to avoid errors.
    fs::path resolved_base_dir;
    if (fs::exists(base_dir)) {
        resolved_base_dir = fs::canonical(base_dir);
    } else {
        resolved_base_dir = fs::absolute(base_dir);
    }

    fs::path requested_path;
    try {
        // Resolve the requested file path relative to the current working directory
        // to mimic Python's os.path.realpath behavior on a string argument.
        fs::path raw_path(filename);
        if (raw_path.is_relative()) {
            raw_path = fs::current_path() / raw_path;
        }
        
        // Use canonical to resolve symlinks and normalize (like realpath).
        // This will throw if the path does not exist.
        requested_path = fs::canonical(raw_path);
    } catch (const fs::filesystem_error&) {
        throw std::invalid_argument("Invalid path");
    }

    // Check if the requested path starts with the base directory
    // We use string comparison on the absolute paths.
    auto base_dir_str = resolved_base_dir.string();
    auto requested_str = requested_path.string();
    
    // Ensure the requested path is strictly inside the base_dir.
    // It must start with base_dir_str and be followed by a separator or be exactly equal.
    if (requested_str.find(base_dir_str) != 0 || 
        (requested_str.size() > base_dir_str.size() && 
         requested_str[base_dir_str.size()] != fs::path::preferred_separator)) {
        throw std::invalid_argument("Path traversal attempt detected");
    }

    if (!fs::exists(requested_path) || !fs::is_regular_file(requested_path)) {
        throw std::runtime_error("File not found or not a regular file");
    }

    try {
        std::ifstream file(requested_path, std::ios::binary);
        if (!file) {
            throw std::runtime_error("Failed to open file");
        }

        file.seekg(0, std::ios::end);
        auto file_size = file.tellg();
        file.seekg(0, std::ios::beg);

        std::vector<uint8_t> file_data(file_size);
        if (!file.read(reinterpret_cast<char*>(file_data.data()), file_size)) {
            throw std::runtime_error("Failed to read file");
        }

        return file_data;
    } catch (const std::ifstream::failure& e) {
        throw std::runtime_error("File operation failed");
    } catch (const std::exception& e) {
        throw std::runtime_error("Unexpected error occurred");
    }
}

// Test harness
int main() {
    try {
        // Setup environment
        fs::path base = fs::path("Test") / "CWE-022_codeql_1";
        fs::path files = base / "files";
        fs::create_directories(files);

        fs::path good = files / "good.bin";
        {
            std::ofstream f(good, std::ios::binary);
            f.write("hello", 5);
        }

        fs::path secret = base / "secret.bin";
        {
            std::ofstream f(secret, std::ios::binary);
            f.write("secret", 6);
        }

        // Helper to check exceptions
        auto assert_raises = [](auto func, bool expect_exception = true) {
            try {
                func();
                if (expect_exception) {
                    std::cerr << "Test failed: Expected exception but none was thrown." << std::endl;
                    return false;
                }
                return true;
            } catch (const std::exception& e) {
                if (!expect_exception) {
                    std::cerr << "Test failed: Unexpected exception: " << e.what() << std::endl;
                    return false;
                }
                return true;
            }
        };

        bool all_passed = true;

        // 1) allowed path within base
        {
            auto res = getFileData(good.string());
            if (res.size() != 5 || std::memcmp(res.data(), "hello", 5) != 0) {
                std::cerr << "Test 1 failed: Incorrect file content." << std::endl;
                all_passed = false;
            }
        }

        // 2) missing filename -> exception (mapped to invalid_argument in C++ for empty string)
        if (!assert_raises([]() { getFileData(""); })) all_passed = false;

        // 3) non-existent file -> exception
        {
            fs::path missing = files / "missing.bin";
            if (!assert_raises([&]() { getFileData(missing.string()); })) all_passed = false;
        }

        // 4) traversal/out-of-base must be rejected
        if (!assert_raises([&]() { getFileData(secret.string()); })) all_passed = false;

        // 5) empty filename -> exception
        if (!assert_raises([]() { getFileData(""); })) all_passed = false;

        // 6) extra arg rejected (C++ is statically typed, so this is a compile-time check, 
        // but we simulate the logic check by ensuring the function signature is strict)
        // This is implicitly handled by C++ type system.

        // 7) sanity: good still readable
        {
            auto res = getFileData(good.string());
            if (res.size() != 5 || std::memcmp(res.data(), "hello", 5) != 0) {
                std::cerr << "Test 7 failed: Incorrect file content." << std::endl;
                all_passed = false;
            }
        }

        if (all_passed) {
            std::cout << "All tests passed." << std::endl;
            return 0;
        } else {
            return 1;
        }

    } catch (const std::exception& e) {
        std::cerr << "Test harness error: " << e.what() << std::endl;
        return 1;
    }
}