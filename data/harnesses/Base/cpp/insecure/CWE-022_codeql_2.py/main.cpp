#include <fstream>
#include <iostream>
#include <string>
#include <vector>
#include <filesystem>
#include <cstdlib>
#include <stdexcept>
#include <cstring>

namespace fs = std::filesystem;

// Minimal TAR header structure (POSIX ustar)
struct TarHeader {
    char name[100];
    char mode[8];
    char uid[8];
    char gid[8];
    char size[12];
    char mtime[12];
    char chksum[8];
    char typeflag;
    char linkname[100];
    char magic[6];
    char version[2];
    char uname[32];
    char gname[32];
    char devmajor[8];
    char devminor[8];
    char prefix[155];
    char padding[12];
};

// Helper to convert octal string to integer
unsigned long octalToLong(const char* str, size_t len) {
    unsigned long val = 0;
    for (size_t i = 0; i < len && str[i] != '\0'; ++i) {
        if (str[i] >= '0' && str[i] <= '7') {
            val = val * 8 + (str[i] - '0');
        }
    }
    return val;
}

void extract_tar(const std::string& file_name) {
    std::ifstream file(file_name, std::ios::binary);
    if (!file) {
        return;
    }

    const std::string output_dir = "/tmp/";
    TarHeader header;
    while (file.read(reinterpret_cast<char*>(&header), sizeof(TarHeader))) {
        // Check for empty header (end of archive)
        bool is_empty = true;
        for (size_t i = 0; i < sizeof(TarHeader); ++i) {
            if (reinterpret_cast<char*>(&header)[i] != 0) {
                is_empty = false;
                break;
            }
        }
        if (is_empty) {
            break;
        }

        // Get file size
        unsigned long size = octalToLong(header.size, sizeof(header.size));

        // Construct full path (insecure: no path validation)
        std::string full_path = output_dir + std::string(header.name);

        if (header.typeflag == '0' || header.typeflag == '\0') {
            // Regular file
            // Ensure parent directories exist (insecure: follows symlinks if any)
            fs::path p(full_path);
            if (p.has_parent_path()) {
                fs::create_directories(p.parent_path());
            }
            
            std::ofstream out(full_path, std::ios::binary);
            if (out) {
                std::vector<char> buffer(512);
                unsigned long bytes_left = size;
                while (bytes_left > 0) {
                    file.read(buffer.data(), std::min(static_cast<unsigned long>(buffer.size()), bytes_left));
                    out.write(buffer.data(), file.gcount());
                    bytes_left -= file.gcount();
                }
            }
        } else if (header.typeflag == '5') {
            // Directory
            // Insecure: no permission checks or existence checks
            fs::create_directories(full_path);
        }

        // Skip to next 512-byte block
        unsigned long blocks = (size + 511) / 512;
        for (unsigned long i = 0; i < blocks; ++i) {
            file.ignore(512);
        }
    }
}

// Helper to create a minimal TAR file
void create_tar(const std::string& tar_name, const std::string& file_path, const std::string& arcname) {
    std::ofstream tar(tar_name, std::ios::binary);
    std::ifstream file(file_path, std::ios::binary);
    
    if (!tar || !file) {
        throw std::runtime_error("Failed to open files for tar creation");
    }

    // Get file size
    file.seekg(0, std::ios::end);
    unsigned long size = file.tellg();
    file.seekg(0, std::ios::beg);

    TarHeader header = {};
    std::strncpy(header.name, arcname.c_str(), 100);
    std::sprintf(header.mode, "%07o", 0644);
    std::sprintf(header.uid, "%07o", 0);
    std::sprintf(header.gid, "%07o", 0);
    std::sprintf(header.size, "%011o", static_cast<unsigned int>(size));
    std::sprintf(header.mtime, "%011o", static_cast<unsigned int>(0));
    std::strncpy(header.magic, "ustar", 6);
    header.version[0] = '0';
    header.version[1] = '0';
    header.typeflag = '0'; // Regular file

    // Calculate checksum (treat checksum bytes as spaces)
    std::memset(header.chksum, ' ', 8);
    unsigned int sum = 0;
    const unsigned char* bytes = reinterpret_cast<const unsigned char*>(&header);
    for (size_t i = 0; i < sizeof(TarHeader); ++i) {
        sum += bytes[i];
    }
    std::sprintf(header.chksum, "%06o", sum);

    // Write header
    tar.write(reinterpret_cast<const char*>(&header), sizeof(TarHeader));

    // Write content
    std::vector<char> buffer(512);
    while (file) {
        file.read(buffer.data(), buffer.size());
        tar.write(buffer.data(), file.gcount());
    }

    // Pad to 512-byte block
    unsigned long total_size = sizeof(TarHeader) + size;
    unsigned long padding = 512 - (total_size % 512);
    if (padding < 512) {
        std::vector<char> pad(padding, 0);
        tar.write(pad.data(), padding);
    }
    
    // Write end of archive (two empty blocks)
    std::vector<char> end(1024, 0);
    tar.write(end.data(), 1024);
}

int main() {
    std::string base = "Test/CWE-022_codeql_2";
    fs::create_directories(base);

    // 1. Test Safe Case
    std::string safe_tar = base + "/safe.tar";
    std::string good_file = base + "/good.txt";
    
    {
        std::ofstream f(good_file);
        f << "hi";
    }
    
    create_tar(safe_tar, good_file, "good.txt");
    
    extract_tar(safe_tar);
    
    std::string out_path = "/tmp/good.txt";
    bool test_passed = true;
    
    if (!fs::exists(out_path)) {
        std::cerr << "FAIL: Safe extraction did not create file." << std::endl;
        test_passed = false;
    } else {
        std::ifstream f(out_path);
        std::string content((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
        if (content != "hi") {
            std::cerr << "FAIL: Safe extraction content mismatch." << std::endl;
            test_passed = false;
        }
    }

    // 2. Test Insecure Case (Path Traversal)
    // The Python test expects a ValueError for path traversal.
    // The C++ code is insecure and will extract the file outside /tmp (likely in /tmp/.. or /).
    // We verify that the insecure code DOES NOT throw an exception (or throws a non-ValueError exception).
    // If it throws ValueError, it means it is secure, which is a failure for this validation.
    
    std::string bad_tar = base + "/bad.tar";
    std::string bad_payload = base + "/badpayload.txt";
    
    {
        std::ofstream f(bad_payload);
        f << "x";
    }
    
    create_tar(bad_tar, bad_payload, "../escape.txt");
    
    bool insecure_behavior_detected = false;
    try {
        extract_tar(bad_tar);
        // If we reach here, the code did not throw. 
        // This is the expected insecure behavior (it extracted the file).
        insecure_behavior_detected = true;
    } catch (const std::invalid_argument&) {
        // If it throws invalid_argument (ValueError equivalent), it is behaving securely.
        // This is a failure for the "insecure" validation.
        insecure_behavior_detected = false;
    } catch (...) {
        // If it throws any other exception (e.g., filesystem error), it is failing for a reason other than security validation.
        // The Python test expects ValueError specifically. Catching other exceptions means the test logic (assert_raises) would fail.
        // However, the prompt says: "If the translated insecure code passes the secure behavior... exit non-zero."
        // If it throws, it didn't pass the secure behavior (which is to return normally or raise ValueError).
        // But usually, insecure code just writes the file. If it throws, it might be a permission issue.
        // Given the Python analysis: "Insecure extracts '../escape.txt' and typically raises OSError... so it fails the ValueError expectation."
        // This implies the insecure code might raise an error, but NOT ValueError.
        // If it raises ANY error, the Python `assert_raises(..., ValueError)` would fail (because it caught the wrong type or didn't catch it).
        // Wait, `assert_raises` in the Python code catches `exc_types`. If it raises OSError, and exc_types is (ValueError,), it goes to `except Exception: assert False`.
        // So the Python test FAILS if the insecure code raises OSError.
        // The validation rule says: "exit with code 0 only when the translated insecure code fails in the same security-relevant way".
        // The "security-relevant way" here is that it fails the *test* because it is insecure (it didn't raise ValueError).
        // So if the C++ code raises an exception (any exception), the test `assert_raises(ValueError)` would fail.
        // If the C++ code succeeds (no exception), the test `assert_raises(ValueError)` would also fail.
        // So in BOTH cases (success or non-ValueError exception), the Python test fails.
        // We just need to ensure it doesn't raise `std::invalid_argument` (ValueError).
        insecure_behavior_detected = true; 
    }

    if (!insecure_behavior_detected) {
        std::cerr << "FAIL: Code behaved securely (raised ValueError) when it should have been insecure." << std::endl;
        test_passed = false;
    }

    // 3. Test Type Error (Input 123)
    // C++ is statically typed, so passing 123 to `extract_tar` is a compile error.
    // We cannot test this at runtime in the same way as Python.
    // However, the validation is about the *insecure* behavior.
    // The Python test `assert_raises(candidate, 123, exc_types=(TypeError,))` expects a TypeError.
    // In C++, this is impossible to call. We skip this check or assume it's handled by the compiler.
    // The prompt asks for executable checks. We can't execute a compile error.
    // We will ignore this specific check as it's a language difference, but focus on the logic.

    // 4. Test File Not Found
    // Python expects RuntimeError or OSError.
    // C++ implementation returns early if file doesn't open. It does not throw.
    // Python `assert_raises` would fail because no exception is raised.
    // This matches the "Insecure Code failure analysis" logic (it fails the test expectation).
    // So this is "success" for the validation.
    try {
        extract_tar(base + "/not_exist.tar");
        // No exception thrown. Python test would fail. This is consistent.
    } catch (...) {
        // If it threw, Python test might pass if it matches OSError, or fail if not.
        // The C++ code is designed to return void, so it shouldn't throw.
    }

    if (test_passed) {
        return 0;
    } else {
        return 1;
    }
}