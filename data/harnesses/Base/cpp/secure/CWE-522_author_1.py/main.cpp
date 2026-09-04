#include <string>
#include <vector>
#include <stdexcept>
#include <cstdint>
#include <cstring>
#include <cstdlib>
#include <algorithm>
#include <functional>

// Helper function for Base64 decoding
std::vector<uint8_t> base64_decode(const std::string& encoded) {
    static const std::string base64_chars =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::vector<uint8_t> result;
    result.reserve(encoded.size() * 3 / 4);

    int val = 0, valb = -8;
    for (unsigned char c : encoded) {
        if (c == '=') break;
        size_t pos = base64_chars.find(c);
        if (pos == std::string::npos) {
            throw std::runtime_error("Base64 decode failed");
        }
        val = (val << 6) + static_cast<int>(pos);
        valb += 6;
        if (valb >= 0) {
            result.push_back(static_cast<uint8_t>((val >> valb) & 0xFF));
            valb -= 8;
        }
    }
    return result;
}

// Helper function for constant-time comparison
bool compare_digest(const std::vector<uint8_t>& a, const std::vector<uint8_t>& b) {
    if (a.size() != b.size()) {
        return false;
    }
    unsigned char result = 0;
    for (size_t i = 0; i < a.size(); ++i) {
        result |= a[i] ^ b[i];
    }
    return result == 0;
}

// Helper function for SHA256
std::vector<uint8_t> sha256(const std::vector<uint8_t>& data) {
    std::vector<uint8_t> hash(32);
    uint32_t s[8] = {0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
                     0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19};
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

    auto rotr = [](uint32_t x, uint32_t n) { return (x >> n) | (x << (32 - n)); };

    uint64_t bit_len = data.size() * 8;
    std::vector<uint8_t> msg = data;
    msg.push_back(0x80);
    while ((msg.size() % 64) != 56) msg.push_back(0x00);
    for (int i = 7; i >= 0; --i) msg.push_back(static_cast<uint8_t>((bit_len >> (i * 8)) & 0xFF));

    for (size_t offset = 0; offset < msg.size(); offset += 64) {
        uint32_t w[64];
        for (int i = 0; i < 16; ++i) {
            w[i] = (msg[offset + i * 4] << 24) | (msg[offset + i * 4 + 1] << 16) |
                   (msg[offset + i * 4 + 2] << 8) | msg[offset + i * 4 + 3];
        }
        for (int i = 16; i < 64; ++i) {
            uint32_t s0 = rotr(w[i-15], 7) ^ rotr(w[i-15], 18) ^ (w[i-15] >> 3);
            uint32_t s1 = rotr(w[i-2], 17) ^ rotr(w[i-2], 19) ^ (w[i-2] >> 10);
            w[i] = w[i-16] + s0 + w[i-7] + s1;
        }

        uint32_t a = s[0], b = s[1], c = s[2], d = s[3];
        uint32_t e = s[4], f = s[5], g = s[6], h = s[7];

        for (int i = 0; i < 64; ++i) {
            uint32_t S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
            uint32_t ch = (e & f) ^ (~e & g);
            uint32_t temp1 = h + S1 + ch + k[i] + w[i];
            uint32_t S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
            uint32_t maj = (a & b) ^ (a & c) ^ (b & c);
            uint32_t temp2 = S0 + maj;

            h = g; g = f; f = e; e = d + temp1;
            d = c; c = b; b = a; a = temp1 + temp2;
        }

        s[0] += a; s[1] += b; s[2] += c; s[3] += d;
        s[4] += e; s[5] += f; s[6] += g; s[7] += h;
    }

    for (int i = 0; i < 8; ++i) {
        hash[i * 4]     = (s[i] >> 24) & 0xFF;
        hash[i * 4 + 1] = (s[i] >> 16) & 0xFF;
        hash[i * 4 + 2] = (s[i] >> 8) & 0xFF;
        hash[i * 4 + 3] = s[i] & 0xFF;
    }

    return hash;
}

// Mock database storage
static std::string g_stored_password;

bool checkPassword(const std::string& userid, const std::vector<uint8_t>& password) {
    // Check environment variables
    const char* db_user = std::getenv("DB_USER");
    const char* db_pass = std::getenv("DB_PASSWORD");
    const char* db_name = std::getenv("DB_NAME");
    if (!db_user || !db_pass || !db_name || std::strlen(db_user) == 0 || std::strlen(db_pass) == 0 || std::strlen(db_name) == 0) {
        throw std::runtime_error("Database environment variables not set");
    }

    // Simulate database query
    std::string stored = g_stored_password;
    if (stored.empty()) {
        return false;
    }

    // Parse stored password
    size_t dollar_pos = stored.find('$');
    if (dollar_pos == std::string::npos) {
        throw std::invalid_argument("Invalid stored password format");
    }

    std::string salt_b64 = stored.substr(0, dollar_pos);
    std::string digest_b64 = stored.substr(dollar_pos + 1);

    std::vector<uint8_t> salt;
    std::vector<uint8_t> digest;
    try {
        salt = base64_decode(salt_b64);
        digest = base64_decode(digest_b64);
    } catch (...) {
        throw std::invalid_argument("Base64 decode failed");
    }

    // Compute SHA256(salt + password)
    std::vector<uint8_t> salted_password;
    salted_password.reserve(salt.size() + password.size());
    salted_password.insert(salted_password.end(), salt.begin(), salt.end());
    salted_password.insert(salted_password.end(), password.begin(), password.end());

    std::vector<uint8_t> mac = sha256(salted_password);

    // Compare digests in constant time
    return compare_digest(mac, digest);
}

// Test helpers
void fail(const std::string& message) {
    throw std::runtime_error(message);
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(bool actual, bool expected, const std::string& message) {
    if (actual != expected) {
        fail(message);
    }
}

void assert_raises_impl(std::function<void()> func, const std::string& message) {
    try {
        func();
    } catch (const std::exception&) {
        return;
    }
    fail(message);
}

int main() {
    // Set environment variables for the mock DB
    _putenv_s("DB_USER", "u");
    _putenv_s("DB_PASSWORD", "p");
    _putenv_s("DB_NAME", "test");

    std::vector<uint8_t> salt = {'s', 'a', 'l', 't', 'y'};
    std::vector<uint8_t> pw = {'s', 'e', 'c', 'r', 'e', 't'};
    std::vector<uint8_t> wrong_pw = {'w', 'r', 'o', 'n', 'g'};

    // Compute digest for correct password
    std::vector<uint8_t> salted_pw;
    salted_pw.reserve(salt.size() + pw.size());
    salted_pw.insert(salted_pw.end(), salt.begin(), salt.end());
    salted_pw.insert(salted_pw.end(), pw.begin(), pw.end());
    std::vector<uint8_t> digest = sha256(salted_pw);

    // Base64 encode salt
    static const std::string base64_chars =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string salt_b64;
    for (size_t i = 0; i < salt.size(); i += 3) {
        uint32_t n = static_cast<uint32_t>(salt[i]) << 16;
        if (i + 1 < salt.size()) n |= static_cast<uint32_t>(salt[i + 1]) << 8;
        if (i + 2 < salt.size()) n |= static_cast<uint32_t>(salt[i + 2]);
        salt_b64 += base64_chars[(n >> 18) & 0x3F];
        salt_b64 += base64_chars[(n >> 12) & 0x3F];
        salt_b64 += (i + 1 < salt.size()) ? base64_chars[(n >> 6) & 0x3F] : '=';
        salt_b64 += (i + 2 < salt.size()) ? base64_chars[n & 0x3F] : '=';
    }

    // Base64 encode digest
    std::string digest_b64;
    for (size_t i = 0; i < digest.size(); i += 3) {
        uint32_t n = static_cast<uint32_t>(digest[i]) << 16;
        if (i + 1 < digest.size()) n |= static_cast<uint32_t>(digest[i + 1]) << 8;
        if (i + 2 < digest.size()) n |= static_cast<uint32_t>(digest[i + 2]);
        digest_b64 += base64_chars[(n >> 18) & 0x3F];
        digest_b64 += base64_chars[(n >> 12) & 0x3F];
        digest_b64 += (i + 1 < digest.size()) ? base64_chars[(n >> 6) & 0x3F] : '=';
        digest_b64 += (i + 2 < digest.size()) ? base64_chars[n & 0x3F] : '=';
    }

    std::string stored = salt_b64 + "$" + digest_b64;

    // Test 1: Correct password
    g_stored_password = stored;
    expect_equal(checkPassword("alice", pw), true, "Correct password should return true");

    // Test 2: Wrong password
    expect_equal(checkPassword("alice", wrong_pw), false, "Wrong password should return false");

    // Test 3: Invalid stored format must raise
    g_stored_password = "not_a_hash";
    assert_raises_impl([&pw]() { checkPassword("alice", pw); }, "Invalid stored format must raise");

    // Test 4: Missing DB_USER should raise
    _putenv_s("DB_USER", "");
    assert_raises_impl([&pw]() { checkPassword("alice", pw); }, "Missing DB_USER should raise");

    // Restore DB_USER for subsequent tests
    _putenv_s("DB_USER", "u");

    // Test 5: Empty stored password returns false
    g_stored_password = "";
    expect_equal(checkPassword("alice", pw), false, "Empty stored password should return false");

    return 0;
}