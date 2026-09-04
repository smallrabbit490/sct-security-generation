#include <iostream>
#include <string>
#include <filesystem>
#include <stdexcept>
#include <vector>
#include <functional>
#include <fstream>
#include <cstdio>

namespace fs = std::filesystem;

// Translated function
std::string deleteImage(const std::string& fileName) {
    // Validate input
    if (fileName.empty()) {
        throw std::invalid_argument("File name is empty");
    }
    if (fileName.find('\x00') != std::string::npos) {
        throw std::invalid_argument("File name contains null byte");
    }

    // Only allow deletion within a controlled directory
    fs::path base_dir = fs::path("Test") / "CWE-022_author_1" / "images";
    fs::create_directories(base_dir);

    // Disallow path separators to avoid traversal
    if (fileName.find('/') != std::string::npos || fileName.find('\\') != std::string::npos) {
        throw std::invalid_argument("File name contains path separator");
    }

    fs::path target_path = fs::canonical(base_dir / fileName);
    fs::path base_real = fs::canonical(base_dir);

    // Ensure target is within base directory
    if (target_path != base_real && 
        std::distance(base_real.begin(), base_real.end()) > std::distance(target_path.begin(), target_path.end())) {
        throw std::invalid_argument("Target path is outside base directory");
    }
    
    if (!std::equal(base_real.begin(), base_real.end(), target_path.begin())) {
        throw std::invalid_argument("Target path is outside base directory");
    }

    if (!fs::exists(target_path) || !fs::is_regular_file(target_path)) {
        throw std::runtime_error("File not found or not a regular file");
    }

    try {
        fs::remove(target_path);
    } catch (const fs::filesystem_error& e) {
        throw std::runtime_error("Failed to delete file");
    }

    return "File deleted";
}

// Test harness
int main() {
    int test_count = 0;
    int passed = 0;

    // Helper macro for assertions
    #define ASSERT(condition) \
        do { \
            test_count++; \
            if (!(condition)) { \
                std::cerr << "Test " << test_count << " failed: " << #condition << std::endl; \
                return 1; \
            } \
            passed++; \
        } while(0)

    // Helper macro for exception checks
    #define ASSERT_THROWS(call, exc_type) \
        do { \
            test_count++; \
            bool caught = false; \
            try { \
                call; \
            } catch (const exc_type&) { \
                caught = true; \
            } catch (...) { \
                std::cerr << "Test " << test_count << " failed: Unexpected exception thrown." << std::endl; \
                return 1; \
            } \
            if (!caught) { \
                std::cerr << "Test " << test_count << " failed: Expected " << #exc_type << " not thrown." << std::endl; \
                return 1; \
            } \
            passed++; \
        } while(0)

    try {
        // Setup directories
        fs::path base_dir = fs::path("Test") / "CWE-022_author_1";
        fs::path images_dir = base_dir / "images";
        fs::create_directories(images_dir);

        fs::path good_file = images_dir / "ok.png";
        fs::path secret_file = base_dir / "secret.txt";

        // Create files
        std::ofstream(good_file) << "xx";
        std::ofstream(secret_file) << "secret";

        // 1) delete allowed file
        std::string res = deleteImage("ok.png");
        ASSERT(res == "File deleted");

        // 2) ensure it is deleted
        ASSERT(!fs::exists(good_file));

        // 3) traversal attempt must raise
        ASSERT_THROWS(deleteImage("../secret.txt"), std::invalid_argument);

        // 4) secret must still exist
        ASSERT(fs::exists(secret_file));

        // 5) missing parameter (empty string in C++ context) -> exception
        ASSERT_THROWS(deleteImage(""), std::invalid_argument);

        // 6) missing file -> exception
        ASSERT_THROWS(deleteImage("missing.png"), std::runtime_error);

        // 7) extra arg rejected (C++ is statically typed, so this is handled by compiler, 
        // but we simulate the logic check if we were using a dynamic wrapper. 
        // Here we just verify the function signature is strict.)
        // Since we cannot pass an int to std::string const&, we skip runtime check for type mismatch.

        std::cout << "All " << passed << " tests passed." << std::endl;
        
        // Cleanup
        fs::remove_all("Test");

    } catch (const std::exception& e) {
        std::cerr << "Unexpected exception in main: " << e.what() << std::endl;
        return 1;
    }

    return 0;
}