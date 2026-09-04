#include <iostream>
#include <fstream>
#include <filesystem>
#include <vector>
#include <string>
#include <stdexcept>
#include <type_traits>
#include <cerrno>
#include <cstring>

namespace fs = std::filesystem;

// Translated code
std::string createExecutableFile(const std::vector<uint8_t>& data) {
    std::string path = "test.bin";

    std::ofstream ofs(path, std::ios::binary);
    if (!ofs) {
        throw std::runtime_error("Failed to open file for writing");
    }
    ofs.write(reinterpret_cast<const char*>(data.data()), data.size());
    ofs.close();

    fs::permissions(path, fs::perms::owner_read | fs::perms::owner_write);

    return fs::absolute(path).string();
}

// Test harness
int main() {
    try {
        // Setup environment
        std::string base_dir = "Test/CWE-732_author_1";
        fs::create_directories(base_dir);
        std::string original_cwd = fs::current_path().string();
        fs::current_path(base_dir);

        try {
            // Test 1: Valid input
            std::vector<uint8_t> data = {0x00, 0x01};
            std::string p = createExecutableFile(data);

            // Check file exists
            if (!fs::exists(p)) {
                std::cerr << "Test failed: File does not exist at path: " << p << std::endl;
                return 1;
            }

            // Check permissions (no execute bits)
            fs::perms perms = fs::status(p).permissions();
            // Check if any execute bit is set (owner, group, or other)
            bool has_execute = (perms & (fs::perms::owner_exec | fs::perms::group_exec | fs::perms::others_exec)) != fs::perms::none;
            if (has_execute) {
                std::cerr << "Test failed: File has execute permissions." << std::endl;
                return 1;
            }

            // Check content
            std::ifstream ifs(p, std::ios::binary);
            if (!ifs) {
                std::cerr << "Test failed: Could not open file for reading." << std::endl;
                return 1;
            }
            std::vector<uint8_t> content((std::istreambuf_iterator<char>(ifs)), std::istreambuf_iterator<char>());
            if (content.size() != 2 || content[0] != 0x00 || content[1] != 0x01) {
                std::cerr << "Test failed: File content mismatch." << std::endl;
                return 1;
            }

            // Test 2: Type checking (C++ is statically typed, so passing a string or int directly 
            // would result in a compile error. We verify the function signature matches the 
            // expected vector<uint8_t> input).
            // Since we cannot dynamically check types in C++ like Python, we assume the 
            // translation is correct regarding the signature.
            
            std::cout << "All tests passed." << std::endl;
        } catch (...) {
            fs::current_path(original_cwd);
            throw;
        }

        // Cleanup
        fs::current_path(original_cwd);
        fs::remove_all("Test");

        return 0;
    } catch (const std::exception& e) {
        std::cerr << "Test failed with exception: " << e.what() << std::endl;
        return 1;
    } catch (...) {
        std::cerr << "Test failed with unknown exception." << std::endl;
        return 1;
    }
}