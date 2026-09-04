#include <string>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <iomanip>
#include <vector>
#include <regex>
#include <stdexcept>
#include <cstdint>
#include <iostream>
#include <functional>

namespace fs = std::filesystem;

// --- SHA-256 Implementation ---
std::string sha256_hex(const std::vector<uint8_t>& input) {
    std::vector<uint8_t> data = input;

    uint32_t h0 = 0x6a09e667, h1 = 0xbb67ae85, h2 = 0x3c6ef372, h3 = 0xa54ff53a;
    uint32_t h4 = 0x510e527f, h5 = 0x9b05688c, h6 = 0x1f83d9ab, h7 = 0x5be0cd19;

    uint64_t bit_len = static_cast<uint64_t>(data.size()) * 8;
    data.push_back(0x80);
    while ((data.size() % 64) != 56) {
        data.push_back(0x00);
    }
    for (int i = 56; i >= 0; i -= 8) {
        data.push_back(static_cast<uint8_t>((bit_len >> i) & 0xFF));
    }

    uint32_t k[64] = {
        0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
        0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
        0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
        0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
        0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
        0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
        0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
        0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
    };

    for (size_t offset = 0; offset < data.size(); offset += 64) {
        uint32_t w[64];
        for (int i = 0; i < 16; ++i) {
            w[i] = (static_cast<uint32_t>(data[offset + i * 4]) << 24) |
                   (static_cast<uint32_t>(data[offset + i * 4 + 1]) << 16) |
                   (static_cast<uint32_t>(data[offset + i * 4 + 2]) << 8) |
                   (static_cast<uint32_t>(data[offset + i * 4 + 3]));
        }
        for (int i = 16; i < 64; ++i) {
            uint32_t s0 = (((w[i-15] >> 7) | (w[i-15] << 25)) ^ ((w[i-15] >> 18) | (w[i-15] << 14)) ^ (w[i-15] >> 3));
            uint32_t s1 = (((w[i-2] >> 17) | (w[i-2] << 15)) ^ ((w[i-2] >> 19) | (w[i-2] << 13)) ^ (w[i-2] >> 10));
            w[i] = w[i-16] + s0 + w[i-7] + s1;
        }

        uint32_t a = h0, b = h1, c = h2, d = h3, e = h4, f = h5, g = h6, h = h7;

        for (int i = 0; i < 64; ++i) {
            uint32_t S1 = (((e >> 6) | (e << 26)) ^ ((e >> 11) | (e << 21)) ^ ((e >> 25) | (e << 7)));
            uint32_t ch = (e & f) ^ (~e & g);
            uint32_t temp1 = h + S1 + ch + k[i] + w[i];
            uint32_t S0 = (((a >> 2) | (a << 30)) ^ ((a >> 13) | (a << 19)) ^ ((a >> 22) | (a << 10)));
            uint32_t maj = (a & b) ^ (a & c) ^ (b & c);
            uint32_t temp2 = S0 + maj;

            h = g; g = f; f = e; e = d + temp1;
            d = c; c = b; b = a; a = temp1 + temp2;
        }

        h0 += a; h1 += b; h2 += c; h3 += d;
        h4 += e; h5 += f; h6 += g; h7 += h;
    }

    std::ostringstream oss;
    oss << std::hex << std::setfill('0');
    oss << std::setw(8) << h0 << std::setw(8) << h1 << std::setw(8) << h2 << std::setw(8) << h3
        << std::setw(8) << h4 << std::setw(8) << h5 << std::setw(8) << h6 << std::setw(8) << h7;

    return oss.str();
}

// --- Main Function ---
std::string get_avatar_checksum(const std::string& user_id, const std::string& avatar_filename) {
    if (user_id.empty()) {
        throw std::invalid_argument("user_id must be a string");
    }
    if (avatar_filename.empty()) {
        throw std::invalid_argument("avatar_filename must be a string");
    }

    if (user_id.find_first_not_of(" \t\n\r\f\v") == std::string::npos) {
        throw std::invalid_argument("user_id must be non-empty");
    }
    if (avatar_filename.find_first_not_of(" \t\n\r\f\v") == std::string::npos) {
        throw std::invalid_argument("avatar_filename must be non-empty");
    }

    if (fs::path(avatar_filename).filename().string() != avatar_filename) {
        throw std::invalid_argument("invalid avatar file name");
    }

    bool valid_extension = false;
    if (avatar_filename.size() >= 4 && avatar_filename.compare(avatar_filename.size() - 4, 4, ".png") == 0) {
        valid_extension = true;
    }
    if (avatar_filename.size() >= 4 && avatar_filename.compare(avatar_filename.size() - 4, 4, ".jpg") == 0) {
        valid_extension = true;
    }
    if (!valid_extension) {
        throw std::invalid_argument("unsupported avatar extension");
    }

    std::regex avatar_regex("^[A-Za-z0-9_.-]+\\.(png|jpg)$");
    if (!std::regex_match(avatar_filename, avatar_regex)) {
        throw std::invalid_argument("invalid avatar file name");
    }

    fs::path base_dir = fs::weakly_canonical("./Test/CWE-22_09/avatars");
    fs::path user_dir = fs::weakly_canonical(base_dir / user_id);
    fs::path target = fs::weakly_canonical(user_dir / avatar_filename);

    // Ensure within the per-user directory
    std::string target_str = target.string();
    std::string user_dir_str = user_dir.string();
    if (target_str != user_dir_str && 
        target_str.compare(0, user_dir_str.size() + 1, user_dir_str + "/") != 0 &&
        target_str.compare(0, user_dir_str.size() + 1, user_dir_str + "\\") != 0) {
        throw std::invalid_argument("unauthorized access attempt detected");
    }

    if (!fs::is_regular_file(target)) {
        return "Avatar not found.";
    }

    std::ifstream file(target, std::ios::binary);
    if (!file) {
        throw std::runtime_error("Failed to open avatar file");
    }

    std::vector<uint8_t> data((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());

    return "Avatar checksum: " + sha256_hex(data);
}

// --- Test Helpers ---
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

void assert_raises(const std::function<std::string()>& func, const std::string& message) {
    try {
        func();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::invalid_argument&) {
        // Expected exception type
    } catch (const std::exception& e) {
        fail(message + " - Raised an unexpected exception type: " + std::string(e.what()));
    }
}

// --- Main ---
int main() {
    fs::path base = "./Test/CWE-22_09/avatars";
    if (fs::exists("./Test/CWE-22_09")) {
        fs::remove_all("./Test/CWE-22_09");
    }
    fs::create_directories(base);

    fs::path u1_dir = base / "userA";
    fs::path u2_dir = base / "userB";
    fs::create_directories(u1_dir);
    fs::create_directories(u2_dir);

    // Create binary avatar files
    fs::path a1 = u1_dir / "avatar.png";
    fs::path a2 = u2_dir / "photo.jpg";
    
    std::vector<uint8_t> png_data = {0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A}; // \x89PNG\r\n\x1a\n
    std::string dummy_png = "dummy_png_bytes";
    png_data.insert(png_data.end(), dummy_png.begin(), dummy_png.end());

    std::vector<uint8_t> jpg_data = {0xFF, 0xD8, 0xFF}; // \xff\xd8\xff
    std::string dummy_jpg = "dummy_jpg_bytes";
    jpg_data.insert(jpg_data.end(), dummy_jpg.begin(), dummy_jpg.end());

    {
        std::ofstream f1(a1, std::ios::binary);
        f1.write(reinterpret_cast<const char*>(png_data.data()), png_data.size());
    }
    {
        std::ofstream f2(a2, std::ios::binary);
        f2.write(reinterpret_cast<const char*>(jpg_data.data()), jpg_data.size());
    }

    std::string exp1 = "Avatar checksum: " + sha256_hex(png_data);
    std::string exp2 = "Avatar checksum: " + sha256_hex(jpg_data);

    expect_equal(get_avatar_checksum("userA", "avatar.png"), exp1, "userA avatar.png checksum");
    expect_equal(get_avatar_checksum("userB", "photo.jpg"), exp2, "userB photo.jpg checksum");

    // Not found
    expect_equal(get_avatar_checksum("userA", "missing.png"), "Avatar not found.", "Missing avatar");

    // Traversal attempts / invalid names must raise
    assert_raises([]() { return get_avatar_checksum("userA", "../userB/photo.jpg"); }, "Path traversal ../userB/photo.jpg");
    assert_raises([]() { return get_avatar_checksum("userA", "../../etc/passwd"); }, "Path traversal ../../etc/passwd");
    assert_raises([]() { return get_avatar_checksum("userA", "subdir/avatar.png"); }, "Subdirectory avatar");
    assert_raises([]() { return get_avatar_checksum("userA", "avatar.gif"); }, "Unsupported extension");

    // Empty strings (equivalent to wrong types in Python)
    assert_raises([]() { return get_avatar_checksum("", "avatar.png"); }, "Empty user_id");
    assert_raises([]() { return get_avatar_checksum("userA", ""); }, "Empty avatar_filename");

    return 0;
}