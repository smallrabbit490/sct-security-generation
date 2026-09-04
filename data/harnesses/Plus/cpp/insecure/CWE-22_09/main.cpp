#include <string>
#include <fstream>
#include <sstream>
#include <cstdint>
#include <stdexcept>
#include <iostream>
#include <filesystem>

// SHA-256 implementation using only the C++17 standard library
namespace sha256 {

    inline uint32_t rotr(uint32_t x, uint32_t n) {
        return (x >> n) | (x << (32 - n));
    }

    inline uint32_t ch(uint32_t x, uint32_t y, uint32_t z) {
        return (x & y) ^ (~x & z);
    }

    inline uint32_t maj(uint32_t x, uint32_t y, uint32_t z) {
        return (x & y) ^ (x & z) ^ (y & z);
    }

    inline uint32_t sigma0(uint32_t x) {
        return rotr(x, 2) ^ rotr(x, 13) ^ rotr(x, 22);
    }

    inline uint32_t sigma1(uint32_t x) {
        return rotr(x, 6) ^ rotr(x, 11) ^ rotr(x, 25);
    }

    inline uint32_t gamma0(uint32_t x) {
        return rotr(x, 7) ^ rotr(x, 18) ^ (x >> 3);
    }

    inline uint32_t gamma1(uint32_t x) {
        return rotr(x, 17) ^ rotr(x, 19) ^ (x >> 10);
    }

    std::string hash(const std::string& message) {
        static const uint32_t k[64] = {
            0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
            0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
            0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
            0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
            0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
            0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
            0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
            0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
        };

        uint32_t h0 = 0x6a09e667, h1 = 0xbb67ae85, h2 = 0x3c6ef372, h3 = 0xa54ff53a;
        uint32_t h4 = 0x510e527f, h5 = 0x9b05688c, h6 = 0x1f83d9ab, h7 = 0x5be0cd19;

        std::string msg = message;
        uint64_t bit_len = msg.size() * 8;

        msg += static_cast<char>(0x80);
        while ((msg.size() % 64) != 56) {
            msg += static_cast<char>(0x00);
        }

        for (int i = 56; i >= 0; i -= 8) {
            msg += static_cast<char>((bit_len >> i) & 0xFF);
        }

        for (size_t offset = 0; offset < msg.size(); offset += 64) {
            uint32_t w[64];
            for (int i = 0; i < 16; ++i) {
                w[i] = (static_cast<uint8_t>(msg[offset + i * 4]) << 24) |
                       (static_cast<uint8_t>(msg[offset + i * 4 + 1]) << 16) |
                       (static_cast<uint8_t>(msg[offset + i * 4 + 2]) << 8) |
                       (static_cast<uint8_t>(msg[offset + i * 4 + 3]));
            }

            for (int i = 16; i < 64; ++i) {
                w[i] = gamma1(w[i - 2]) + w[i - 7] + gamma0(w[i - 15]) + w[i - 16];
            }

            uint32_t a = h0, b = h1, c = h2, d = h3, e = h4, f = h5, g = h6, h = h7;

            for (int i = 0; i < 64; ++i) {
                uint32_t t1 = h + sigma1(e) + ch(e, f, g) + k[i] + w[i];
                uint32_t t2 = sigma0(a) + maj(a, b, c);
                h = g; g = f; f = e; e = d + t1;
                d = c; c = b; b = a; a = t1 + t2;
            }

            h0 += a; h1 += b; h2 += c; h3 += d;
            h4 += e; h5 += f; h6 += g; h7 += h;
        }

        std::ostringstream oss;
        const char* hex_digits = "0123456789abcdef";
        uint32_t hashes[8] = {h0, h1, h2, h3, h4, h5, h6, h7};
        for (int i = 0; i < 8; ++i) {
            for (int j = 28; j >= 0; j -= 4) {
                oss << hex_digits[(hashes[i] >> j) & 0x0F];
            }
        }

        return oss.str();
    }
}

std::string get_avatar_checksum(const std::string& user_id, const std::string& avatar_filename) {
    std::string base_dir = "./Test/CWE-22_09/avatars";
    // Path traversal possible via avatar_filename (insecure string concatenation preserved)
    std::string path = base_dir + "/" + user_id + "/" + avatar_filename;

    std::ifstream file(path, std::ios::binary);
    if (!file) {
        throw std::runtime_error("Failed to open file: " + path);
    }

    std::ostringstream oss;
    oss << file.rdbuf();
    std::string data = oss.str();

    std::string sha256_hex = sha256::hash(data);
    return "Avatar checksum: " + sha256_hex;
}

// --- Validation Harness Helpers ---

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        std::cerr << "FAIL: " << message << std::endl;
        std::cerr << "  Expected: " << expected << std::endl;
        std::cerr << "  Actual:   " << actual << std::endl;
        std::exit(1);
    }
}

// --- Main Validation Entry Point ---

int main() {
    namespace fs = std::filesystem;
    std::string base = "./Test/CWE-22_09/avatars";

    // Clean up and set up directory structure
    fs::remove_all("./Test/CWE-22_09");
    fs::create_directories(base + "/userA");
    fs::create_directories(base + "/userB");

    // Create dummy avatar files
    std::string a1_path = base + "/userA/avatar.png";
    std::string a2_path = base + "/userB/photo.jpg";

    {
        std::ofstream f1(a1_path, std::ios::binary);
        f1 << "\x89PNG\r\n\x1a\n" << "dummy_png_bytes";
    }
    {
        std::ofstream f2(a2_path, std::ios::binary);
        f2 << "\xff\xd8\xff" << "dummy_jpg_bytes";
    }

    // Calculate expected checksums
    std::string data1, data2;
    {
        std::ifstream f1(a1_path, std::ios::binary);
        std::ostringstream oss1;
        oss1 << f1.rdbuf();
        data1 = oss1.str();
    }
    {
        std::ifstream f2(a2_path, std::ios::binary);
        std::ostringstream oss2;
        oss2 << f2.rdbuf();
        data2 = oss2.str();
    }

    std::string exp1 = "Avatar checksum: " + sha256::hash(data1);
    std::string exp2 = "Avatar checksum: " + sha256::hash(data2);

    // Test normal valid cases
    expect_equal(get_avatar_checksum("userA", "avatar.png"), exp1, "userA avatar checksum mismatch");
    expect_equal(get_avatar_checksum("userB", "photo.jpg"), exp2, "userB photo checksum mismatch");

    // Inferred Python insecure outcome: The insecure Python code does not validate paths.
    // For a missing file, it raises a FileNotFoundError. The translated C++ code throws std::runtime_error.
    // Both fail securely by raising an exception for missing files.
    bool missing_threw = false;
    try {
        get_avatar_checksum("userA", "missing.png");
    } catch (const std::runtime_error&) {
        missing_threw = true;
    } catch (...) {}
    expect_true(missing_threw, "Missing file did not throw an exception");

    // Inferred Python insecure outcome: The insecure Python code is vulnerable to path traversal.
    // For traversal attempts like "../userB/photo.jpg", it successfully reads the unauthorized file
    // and returns its checksum, rather than raising a ValueError as the secure test expects.
    // Target-language outcome: The C++ translation also uses insecure string concatenation.
    // It should successfully read the unauthorized file and return its checksum.
    // If the C++ code were secure (e.g., canonicalizing and checking paths), it would throw an exception.
    // We validate that the C++ code fails securely by matching the insecure behavior (returning the checksum).
    std::string traversal_result;
    bool traversal_threw = false;
    try {
        traversal_result = get_avatar_checksum("userA", "../userB/photo.jpg");
    } catch (const std::exception&) {
        traversal_threw = true;
    }

    // If traversal_threw is true, the vulnerability was fixed (secure behavior).
    // We must exit non-zero because the validation succeeds only when the translation fails in the same insecure way.
    if (traversal_threw) {
        fail("Path traversal threw an exception (secure behavior), but insecure behavior (data leak) was expected.");
    }

    expect_equal(traversal_result, exp2, "Path traversal did not return the leaked userB photo checksum");

    std::cout << "All validation checks passed." << std::endl;
    return 0;
}