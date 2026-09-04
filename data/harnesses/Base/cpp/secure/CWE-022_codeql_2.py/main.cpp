#include <iostream>
#include <fstream>
#include <string>
#include <vector>
#include <memory>
#include <cstring>
#include <stdexcept>
#include <system_error>
#include <filesystem>
#include <algorithm>
#include <cstdio>

namespace fs = std::filesystem;

// Minimal TAR parser for extracting files securely
class TarExtractor {
private:
    std::ifstream file;
    std::string base_path;

    struct TarHeader {
        char name[100];
        char mode[8];
        char uid[8];
        char gid[8];
        char size[12];
        char mtime[12];
        char checksum[8];
        char typeflag[1];
        char linkname[100];
        char magic[6];
        char version[2];
        char uname[32];
        char gname[32];
        char devmajor[8];
        char devminor[8];
        char prefix[155];
    };

    static size_t parse_octal(const char* str, size_t len) {
        size_t result = 0;
        for (size_t i = 0; i < len && str[i] != '\0'; ++i) {
            if (str[i] >= '0' && str[i] <= '7') {
                result = result * 8 + (str[i] - '0');
            }
        }
        return result;
    }

    void validate_path(const std::string& name) {
        if (name.empty()) {
            throw std::invalid_argument("Empty path");
        }

        // Check for absolute paths
        if (fs::path(name).is_absolute()) {
            throw std::invalid_argument("Absolute path detected");
        }

        // Normalize the path
        fs::path norm_path = fs::path(name).lexically_normal();

        // Check for parent directory references
        std::string norm_str = norm_path.string();
        if (norm_str == ".." || norm_str.find("..") == 0) {
            throw std::invalid_argument("Path traversal attempt");
        }

        // Check for ".." in any component
        for (const auto& part : norm_path) {
            if (part == "..") {
                throw std::invalid_argument("Path traversal attempt");
            }
        }
    }

public:
    TarExtractor(const std::string& filename, const std::string& extract_path)
        : base_path(extract_path) {
        file.open(filename, std::ios::binary);
        if (!file) {
            throw std::runtime_error("Failed to open tar file");
        }
    }

    void extract() {
        TarHeader header;
        std::vector<char> buffer(512);

        while (file.read(reinterpret_cast<char*>(&header), 512)) {
            // Check for end of archive (all zeros)
            if (header.name[0] == '\0') {
                bool all_zero = true;
                for (size_t i = 0; i < 512; ++i) {
                    if (reinterpret_cast<char*>(&header)[i] != '\0') {
                        all_zero = false;
                        break;
                    }
                }
                if (all_zero) {
                    // Check another block for full end marker
                    if (file.read(buffer.data(), 512)) {
                        bool second_zero = true;
                        for (size_t i = 0; i < 512; ++i) {
                            if (buffer[i] != '\0') {
                                second_zero = false;
                                break;
                            }
                        }
                        if (second_zero) {
                            break;
                        } else {
                            file.seekg(-512, std::ios::cur);
                        }
                    }
                    continue;
                }
            }

            // Parse file size
            size_t size = parse_octal(header.size, 12);

            // Get the full path (including prefix)
            std::string full_name;
            if (header.prefix[0] != '\0') {
                full_name = std::string(header.prefix, strnlen(header.prefix, 155)) + "/" + 
                           std::string(header.name, strnlen(header.name, 100));
            } else {
                full_name = std::string(header.name, strnlen(header.name, 100));
            }

            // Validate the path
            validate_path(full_name);

            // Construct the destination path
            fs::path dest_path = fs::path(base_path) / full_name;

            // Create parent directories if needed
            if (header.typeflag[0] == '0' || header.typeflag[0] == '\0') {
                // Regular file
                fs::create_directories(dest_path.parent_path());
                
                std::ofstream out_file(dest_path, std::ios::binary);
                if (!out_file) {
                    throw std::runtime_error("Failed to create output file");
                }

                // Write file content
                size_t remaining = size;
                while (remaining > 0) {
                    size_t to_read = std::min(remaining, buffer.size());
                    file.read(buffer.data(), to_read);
                    out_file.write(buffer.data(), file.gcount());
                    remaining -= file.gcount();
                }
                out_file.close();
            } else if (header.typeflag[0] == '5') {
                // Directory
                fs::create_directories(dest_path);
            }

            // Skip to next 512-byte block
            size_t skip = (512 - (size % 512)) % 512;
            if (skip > 0) {
                file.read(buffer.data(), skip);
            }
        }
    }
};

void extract_tar(const std::string& file_name) {
    try {
        TarExtractor extractor(file_name, "/tmp");
        extractor.extract();
    } catch (const std::invalid_argument& e) {
        throw;
    } catch (const std::exception& e) {
        throw std::runtime_error(e.what());
    }
}

// Helper to create a simple TAR file
void create_simple_tar(const std::string& tar_path, const std::string& content_path, const std::string& arcname) {
    std::ofstream tar(tar_path, std::ios::binary);
    std::ifstream content(content_path, std::ios::binary);
    
    if (!tar || !content) {
        throw std::runtime_error("Failed to open files for tar creation");
    }

    // Read content
    std::string file_data((std::istreambuf_iterator<char>(content)), std::istreambuf_iterator<char>());
    size_t size = file_data.size();

    // Prepare Header
    char header[512] = {0};
    
    // Name
    strncpy(header, arcname.c_str(), 100);
    
    // Mode (0000644)
    strncpy(header + 100, "0000644 ", 8);
    
    // Size (octal)
    char size_str[12];
    snprintf(size_str, 12, "%011o", (unsigned int)size);
    strncpy(header + 124, size_str, 12);
    
    // Typeflag (regular file)
    header[156] = '0';
    
    // Magic (ustar)
    strncpy(header + 257, "ustar", 6);

    // Calculate Checksum
    unsigned int checksum = 0;
    for (int i = 0; i < 512; ++i) {
        checksum += (unsigned char)header[i];
    }
    
    // Write checksum into header (bytes 148-155)
    char checksum_str[8];
    snprintf(checksum_str, 8, "%06o ", checksum);
    strncpy(header + 148, checksum_str, 8);

    // Write Header
    tar.write(header, 512);
    
    // Write Data
    tar.write(file_data.data(), size);
    
    // Write Padding
    size_t padding = (512 - (size % 512)) % 512;
    std::vector<char> pad(padding, 0);
    tar.write(pad.data(), padding);
    
    // Write End of Archive (two 512-byte zero blocks)
    std::vector<char> zero_block(512, 0);
    tar.write(zero_block.data(), 512);
    tar.write(zero_block.data(), 512);
}

int main() {
    // Setup test environment
    std::string base_dir = "Test/CWE-022_codeql_2";
    fs::create_directories(base_dir);

    std::string safe_tar = base_dir + "/safe.tar";
    std::string good_txt = base_dir + "/good.txt";
    std::string bad_tar = base_dir + "/bad.tar";
    std::string bad_payload = base_dir + "/badpayload.txt";
    std::string not_exist_tar = base_dir + "/not_exist.tar";

    // Clean up /tmp/good.txt if it exists from previous runs
    fs::remove("/tmp/good.txt");

    // Create test files
    {
        std::ofstream f(good_txt);
        f << "hi";
    }
    {
        std::ofstream f(bad_payload);
        f << "x";
    }

    // Create TAR files
    create_simple_tar(safe_tar, good_txt, "good.txt");
    create_simple_tar(bad_tar, bad_payload, "../escape.txt");

    bool passed = true;

    // Test 1: Safe extraction
    try {
        extract_tar(safe_tar);
        if (!fs::exists("/tmp/good.txt")) {
            std::cerr << "Test 1 Failed: /tmp/good.txt not created" << std::endl;
            passed = false;
        } else {
            std::ifstream f("/tmp/good.txt");
            std::string content((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
            if (content != "hi") {
                std::cerr << "Test 1 Failed: Content mismatch" << std::endl;
                passed = false;
            }
        }
    } catch (const std::exception& e) {
        std::cerr << "Test 1 Failed with exception: " << e.what() << std::endl;
        passed = false;
    }

    // Test 2: Path traversal (should raise ValueError/invalid_argument)
    try {
        extract_tar(bad_tar);
        std::cerr << "Test 2 Failed: Expected ValueError for path traversal" << std::endl;
        passed = false;
    } catch (const std::invalid_argument&) {
        // Expected
    } catch (const std::exception& e) {
        std::cerr << "Test 2 Failed: Wrong exception type: " << e.what() << std::endl;
        passed = false;
    }

    // Test 3: Invalid argument type (C++ is statically typed, so we simulate the check logic if needed, 
    // but the function signature enforces string. The Python test passes an int.
    // In C++, we can't pass int to std::string. We skip this or assume the wrapper handles it.
    // However, the prompt asks for functional checks equivalent to Python tests.
    // Since C++ is statically typed, extract_tar(123) is a compile error.
    // We will assume this test is implicitly satisfied by the type system or not applicable.
    // But to be thorough, we can check if the function logic handles bad inputs if we were using a variant.
    // Given the signature `void extract_tar(const std::string& file_name)`, this is handled by compiler.

    // Test 4: File not found (should raise RuntimeError)
    try {
        extract_tar(not_exist_tar);
        std::cerr << "Test 4 Failed: Expected RuntimeError for missing file" << std::endl;
        passed = false;
    } catch (const std::runtime_error&) {
        // Expected
    } catch (const std::exception& e) {
        std::cerr << "Test 4 Failed: Wrong exception type: " << e.what() << std::endl;
        passed = false;
    }

    // Cleanup
    fs::remove_all(base_dir);
    fs::remove("/tmp/good.txt");

    if (passed) {
        return 0;
    } else {
        return 1;
    }
}