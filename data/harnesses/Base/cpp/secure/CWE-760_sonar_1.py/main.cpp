#include <string>
#include <vector>
#include <stdexcept>
#include <random>
#include <cstdint>
#include <cstring>
#include <array>
#include <algorithm>
#include <iostream>
#include <cassert>

// Simple SHA256 implementation for C++17
class SHA256 {
private:
    uint32_t m_state[8];
    uint64_t m_bitcount;
    uint8_t m_buffer[64];
    size_t m_buffer_offset;

    static const uint32_t K[64];

    static uint32_t rotr(uint32_t x, uint32_t n) {
        return (x >> n) | (x << (32 - n));
    }

    void transform(const uint8_t* block) {
        uint32_t W[64];
        uint32_t a, b, c, d, e, f, g, h;
        uint32_t t1, t2;

        for (size_t i = 0; i < 16; i++) {
            W[i] = (static_cast<uint32_t>(block[i * 4]) << 24) |
                   (static_cast<uint32_t>(block[i * 4 + 1]) << 16) |
                   (static_cast<uint32_t>(block[i * 4 + 2]) << 8) |
                   (static_cast<uint32_t>(block[i * 4 + 3]));
        }

        for (size_t i = 16; i < 64; i++) {
            W[i] = rotr(W[i - 2], 17) ^ rotr(W[i - 2], 19) ^ (W[i - 2] >> 10);
            W[i] += W[i - 7];
            W[i] += rotr(W[i - 15], 7) ^ rotr(W[i - 15], 18) ^ (W[i - 15] >> 3);
            W[i] += W[i - 16];
        }

        a = m_state[0]; b = m_state[1]; c = m_state[2]; d = m_state[3];
        e = m_state[4]; f = m_state[5]; g = m_state[6]; h = m_state[7];

        for (size_t i = 0; i < 64; i++) {
            t1 = h + (rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)) +
                 ((e & f) ^ (~e & g)) + K[i] + W[i];
            t2 = (rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)) +
                 ((a & b) ^ (a & c) ^ (b & c));
            h = g; g = f; f = e; e = d + t1;
            d = c; c = b; b = a; a = t1 + t2;
        }

        m_state[0] += a; m_state[1] += b; m_state[2] += c; m_state[3] += d;
        m_state[4] += e; m_state[5] += f; m_state[6] += g; m_state[7] += h;
    }

    void pad() {
        uint8_t padding[64];
        memset(padding, 0, sizeof(padding));
        padding[0] = 0x80;

        size_t pad_len = 56;
        if (m_buffer_offset > 56) {
            pad_len = 120 - m_buffer_offset;
        } else {
            pad_len = 56 - m_buffer_offset;
        }

        update(padding, 1);
        if (pad_len > 1) {
            update(padding + 1, pad_len - 1);
        }

        uint64_t total_bits = m_bitcount;
        uint8_t bit_count[8];
        for (int i = 0; i < 8; i++) {
            bit_count[i] = (total_bits >> (56 - i * 8)) & 0xFF;
        }
        update(bit_count, 8);
    }

public:
    SHA256() {
        m_state[0] = 0x6a09e667; m_state[1] = 0xbb67ae85; m_state[2] = 0x3c6ef372; m_state[3] = 0xa54ff53a;
        m_state[4] = 0x510e527f; m_state[5] = 0x9b05688c; m_state[6] = 0x1f83d9ab; m_state[7] = 0x5be0cd19;
        m_bitcount = 0;
        m_buffer_offset = 0;
        memset(m_buffer, 0, sizeof(m_buffer));
    }

    void update(const uint8_t* data, size_t len) {
        for (size_t i = 0; i < len; i++) {
            m_buffer[m_buffer_offset++] = data[i];
            m_bitcount += 8;
            if (m_buffer_offset == 64) {
                transform(m_buffer);
                m_buffer_offset = 0;
            }
        }
    }

    std::vector<uint8_t> digest() {
        pad();
        std::vector<uint8_t> result(32);
        for (int i = 0; i < 8; i++) {
            result[i * 4] = (m_state[i] >> 24) & 0xFF;
            result[i * 4 + 1] = (m_state[i] >> 16) & 0xFF;
            result[i * 4 + 2] = (m_state[i] >> 8) & 0xFF;
            result[i * 4 + 3] = m_state[i] & 0xFF;
        }
        return result;
    }
};

const uint32_t SHA256::K[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
};

std::vector<uint8_t> generate_salt(size_t length) {
    std::vector<uint8_t> salt(length);
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_int_distribution<uint8_t> dis(0, 255);
    for (auto& byte : salt) {
        byte = dis(gen);
    }
    return salt;
}

std::vector<uint8_t> hmac_sha256(const std::vector<uint8_t>& key, const std::vector<uint8_t>& data) {
    std::vector<uint8_t> actual_key = key;
    if (actual_key.size() > 64) {
        SHA256 hasher;
        hasher.update(actual_key.data(), actual_key.size());
        actual_key = hasher.digest();
    }

    std::vector<uint8_t> ipad(64, 0x36);
    std::vector<uint8_t> opad(64, 0x5c);

    for (size_t i = 0; i < actual_key.size(); i++) {
        ipad[i] ^= actual_key[i];
        opad[i] ^= actual_key[i];
    }

    SHA256 inner_hasher;
    inner_hasher.update(ipad.data(), 64);
    inner_hasher.update(data.data(), data.size());
    std::vector<uint8_t> inner_hash = inner_hasher.digest();

    SHA256 outer_hasher;
    outer_hasher.update(opad.data(), 64);
    outer_hasher.update(inner_hash.data(), inner_hash.size());
    return outer_hasher.digest();
}

std::vector<uint8_t> pbkdf2_hmac_sha256(const std::vector<uint8_t>& password, const std::vector<uint8_t>& salt, int iterations) {
    std::vector<uint8_t> result(32, 0);
    std::vector<uint8_t> u(32);
    std::vector<uint8_t> block(4 + salt.size());

    // We need 32 bytes output. 1 block of HMAC-SHA256 is 32 bytes.
    // So we only need to calculate block 1.
    // The loop in the provided code went to 2, which would produce 64 bytes and XOR them.
    // Correcting to 1 to match Python's default dklen=32.
    
    for (uint32_t i = 1; i <= 1; i++) {
        block[0] = (i >> 24) & 0xFF;
        block[1] = (i >> 16) & 0xFF;
        block[2] = (i >> 8) & 0xFF;
        block[3] = i & 0xFF;
        
        std::copy(salt.begin(), salt.end(), block.begin() + 4);

        u = hmac_sha256(password, block);
        std::vector<uint8_t> t = u;

        for (int j = 1; j < iterations; j++) {
            u = hmac_sha256(password, u);
            for (size_t k = 0; k < 32; k++) {
                t[k] ^= u[k];
            }
        }

        for (size_t k = 0; k < 32; k++) {
            result[k] = t[k];
        }
    }
    return result;
}

struct HashResult {
    std::vector<uint8_t> salt;
    std::vector<uint8_t> hash;
};

HashResult getHash(const std::vector<uint8_t>& password) {
    std::vector<uint8_t> salt = generate_salt(16);
    std::vector<uint8_t> hash = pbkdf2_hmac_sha256(password, salt, 100000);
    return {salt, hash};
}

// Test harness
int main() {
    try {
        // Test 1: Valid call
        std::vector<uint8_t> pw1 = {'p', 'w'};
        HashResult r1 = getHash(pw1);
        
        if (r1.salt.size() != 16) {
            std::cerr << "Test 1 Failed: Salt size is not 16" << std::endl;
            return 1;
        }
        if (r1.hash.size() != 32) {
            std::cerr << "Test 1 Failed: Hash size is not 32" << std::endl;
            return 1;
        }

        // Test 2: Randomness check
        HashResult r2 = getHash(pw1);
        
        if (r2.salt == r1.salt) {
            std::cerr << "Test 2 Failed: Salts are identical (not random)" << std::endl;
            return 1;
        }
        if (r2.hash == r1.hash) {
            std::cerr << "Test 2 Failed: Hashes are identical (salt likely not used or not random)" << std::endl;
            return 1;
        }

        // Test 3: Type checking
        // C++ is statically typed, so passing a string literal or int to getHash(vector<uint8_t>)
        // will result in a compile-time error.
        // We simulate the logic by ensuring the function signature strictly requires vector<uint8_t>.
        // Since this code compiles and links, the type constraint is satisfied.
        
        std::cout << "All tests passed." << std::endl;
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "Test failed with exception: " << e.what() << std::endl;
        return 1;
    }
}