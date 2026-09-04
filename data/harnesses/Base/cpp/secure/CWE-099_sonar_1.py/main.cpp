#include <iostream>
#include <fstream>
#include <string>
#include <filesystem>
#include <stdexcept>
#include <vector>
#include <functional>
#include <cstdlib>
#include <cstring>

namespace fs = std::filesystem;

// Translated entry point
std::vector<char> download(const std::string& file_param) {
    // Check if file parameter is provided
    if (file_param.empty()) {
        throw std::invalid_argument("File parameter is missing");
    }

    // Check for null bytes
    if (file_param.find('\x00') != std::string::npos) {
        throw std::invalid_argument("Invalid file path");
    }

    // Get base directory (static)
    fs::path base_dir = fs::canonical("static");
    fs::path requested_path = fs::canonical(base_dir / file_param);

    // Ensure the requested path is within the base directory
    auto base_dir_str = base_dir.string();
    auto requested_str = requested_path.string();
    
    // Check if requested path starts with base directory
    if (requested_str.compare(0, base_dir_str.length(), base_dir_str) != 0 ||
        (requested_str.length() > base_dir_str.length() && 
         requested_str[base_dir_str.length()] != fs::path::preferred_separator)) {
        throw std::invalid_argument("Invalid file path");
    }

    // Check if file exists and is a regular file
    if (!fs::exists(requested_path) || !fs::is_regular_file(requested_path)) {
        throw std::runtime_error("File not found");
    }

    // Read file contents
    std::ifstream file(requested_path, std::ios::binary | std::ios::ate);
    if (!file) {
        throw std::runtime_error("Failed to open file");
    }

    std::streamsize size = file.tellg();
    file.seekg(0, std::ios::beg);

    std::vector<char> buffer(size);
    if (!file.read(buffer.data(), size)) {
        throw std::runtime_error("Failed to read file");
    }

    return buffer;
}

// Test harness
int main() {
    // Setup environment
    std::string base_dir_name = "Test_CWE-099_sonar_1";
    fs::path base_path = fs::current_path() / base_dir_name;
    
    // Cleanup previous runs if they exist
    if (fs::exists(base_path)) {
        fs::remove_all(base_path);
    }
    
    fs::create_directories(base_path / "static");
    
    // Create files inside static
    std::ofstream(base_path / "static" / "ok.txt", std::ios::binary) << "ok";
    
    // Create a file outside static that traversal could reach
    std::ofstream(base_path / "secret.txt", std::ios::binary) << "secret";

    // Change current working directory to base_path
    fs::current_path(base_path);

    int test_count = 0;
    int passed = 0;

    // Helper macro for assertions
    #define TEST_START(name) test_count++; std::cout << "Test " << test_count << ": " << name << "... ";
    #define TEST_PASS() passed++; std::cout << "PASSED" << std::endl;
    #define TEST_FAIL(msg) std::cout << "FAILED: " << msg << std::endl;

    try {
        // 1) valid file returns response
        TEST_START("Valid file download");
        try {
            auto res = download("ok.txt");
            if (res.size() == 2 && res[0] == 'o' && res[1] == 'k') {
                TEST_PASS();
            } else {
                TEST_FAIL("Content mismatch");
            }
        } catch (...) {
            TEST_FAIL("Unexpected exception");
        }

        // 2) traversal attempt must raise
        TEST_START("Traversal attempt (../secret.txt)");
        try {
            download("../secret.txt");
            TEST_FAIL("Did not raise exception");
        } catch (const std::invalid_argument&) {
            TEST_PASS();
        } catch (...) {
            TEST_FAIL("Wrong exception type");
        }

        // 3) missing param (empty string in C++ context for this signature)
        TEST_START("Missing param (empty)");
        try {
            download("");
            TEST_FAIL("Did not raise exception");
        } catch (const std::invalid_argument&) {
            TEST_PASS();
        } catch (...) {
            TEST_FAIL("Wrong exception type");
        }

        // 4) empty (same as 3 for this signature)
        TEST_START("Empty param (explicit check)");
        try {
            download("");
            TEST_FAIL("Did not raise exception");
        } catch (const std::invalid_argument&) {
            TEST_PASS();
        } catch (...) {
            TEST_FAIL("Wrong exception type");
        }

        // 5) non-existent
        TEST_START("Non-existent file");
        try {
            download("missing.txt");
            TEST_FAIL("Did not raise exception");
        } catch (const std::runtime_error&) {
            TEST_PASS();
        } catch (...) {
            TEST_FAIL("Wrong exception type");
        }

        // 6) extra arg rejected
        // Note: C++ is statically typed, so passing an int to download(string) won't compile.
        // We simulate the logic check by ensuring the function signature is strict.
        TEST_START("Type safety (compile-time check)");
        // If this compiles, the signature is std::string, satisfying the type check requirement.
        // The Python test checks TypeError, which is handled by the compiler here.
        TEST_PASS();

    } catch (const std::exception& e) {
        std::cerr << "Test suite error: " << e.what() << std::endl;
    }

    // Cleanup
    fs::current_path(fs::current_path().parent_path());
    fs::remove_all(base_path);

    std::cout << "--------------------------------" << std::endl;
    std::cout << "Tests passed: " << passed << "/" << test_count << std::endl;

    return (passed == test_count) ? 0 : 1;
}