#include <string>
#include <iomanip>
#include <sstream>
#include <array>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <cassert>

// Simple MD5 implementation based on RFC 1321
// This preserves the insecure behavior of the original Python code
// which uses hashlib.md5.

class MD5 {
private:
    uint32_t state[4];
    uint32_t count[2];
    uint8_t buffer[64];

    static uint32_t rotate_left(uint32_t x, uint32_t n) {
        return (x << n) | (x >> (32 - n));
    }

    static uint32_t F(uint32_t x, uint32_t y, uint32_t z) {
        return (x & y) | (~x & z);
    }

    static uint32_t G(uint32_t x, uint32_t y, uint32_t z) {
        return (x & z) | (y & ~z);
    }

    static uint32_t H(uint32_t x, uint32_t y, uint32_t z) {
        return x ^ y ^ z;
    }

    static uint32_t I(uint32_t x, uint32_t y, uint32_t z) {
        return y ^ (x | ~z);
    }

    // Macros for MD5 transformation rounds
    #define FF(a, b, c, d, x, s, ac) { \
        (a) += F((b), (c), (d)) + (x) + (ac); \
        (a) = rotate_left((a), (s)); \
        (a) += (b); \
    }
    #define GG(a, b, c, d, x, s, ac) { \
        (a) += G((b), (c), (d)) + (x) + (ac); \
        (a) = rotate_left((a), (s)); \
        (a) += (b); \
    }
    #define HH(a, b, c, d, x, s, ac) { \
        (a) += H((b), (c), (d)) + (x) + (ac); \
        (a) = rotate_left((a), (s)); \
        (a) += (b); \
    }
    #define II(a, b, c, d, x, s, ac) { \
        (a) += I((b), (c), (d)) + (x) + (ac); \
        (a) = rotate_left((a), (s)); \
        (a) += (b); \
    }

    void transform(const uint8_t block[64]) {
        uint32_t a = state[0], b = state[1], c = state[2], d = state[3];
        uint32_t m[64];

        for (int i = 0, j = 0; i < 16; ++i, j += 4) {
            m[i] = (static_cast<uint32_t>(block[j])) |
                   (static_cast<uint32_t>(block[j + 1]) << 8) |
                   (static_cast<uint32_t>(block[j + 2]) << 16) |
                   (static_cast<uint32_t>(block[j + 3]) << 24);
        }

        // Round 1
        FF(a, b, c, d, m[0], 7, 0xd76aa478);
        FF(d, a, b, c, m[1], 12, 0xe8c7b756);
        FF(c, d, a, b, m[2], 17, 0x242070db);
        FF(b, c, d, a, m[3], 22, 0xc1bdceee);
        FF(a, b, c, d, m[4], 7, 0xf57c0faf);
        FF(d, a, b, c, m[5], 12, 0x4787c62a);
        FF(c, d, a, b, m[6], 17, 0xa8304613);
        FF(b, c, d, a, m[7], 22, 0xfd469501);
        FF(a, b, c, d, m[8], 7, 0x698098d8);
        FF(d, a, b, c, m[9], 12, 0x8b44f7af);
        FF(c, d, a, b, m[10], 17, 0xffff5bb1);
        FF(b, c, d, a, m[11], 22, 0x895cd7be);
        FF(a, b, c, d, m[12], 7, 0x6b901122);
        FF(d, a, b, c, m[13], 12, 0xfd987193);
        FF(c, d, a, b, m[14], 17, 0xa679438e);
        FF(b, c, d, a, m[15], 22, 0x49b40821);

        // Round 2
        GG(a, b, c, d, m[1], 5, 0xf61e2562);
        GG(d, a, b, c, m[6], 9, 0xc040b340);
        GG(c, d, a, b, m[11], 14, 0x265e5a51);
        GG(b, c, d, a, m[0], 20, 0xe9b6c7aa);
        GG(a, b, c, d, m[5], 5, 0xd62f105d);
        GG(d, a, b, c, m[10], 9, 0x02441453);
        GG(c, d, a, b, m[15], 14, 0xd8a1e681);
        GG(b, c, d, a, m[4], 20, 0xe7d3fbc8);
        GG(a, b, c, d, m[9], 5, 0x21e1cde6);
        GG(d, a, b, c, m[14], 9, 0xc33707d6);
        GG(c, d, a, b, m[3], 14, 0xf4d50d87);
        GG(b, c, d, a, m[8], 20, 0x455a14ed);
        GG(a, b, c, d, m[13], 5, 0xa9e3e905);
        GG(d, a, b, c, m[2], 9, 0xfcefa3f8);
        GG(c, d, a, b, m[7], 14, 0x676f02d9);
        GG(b, c, d, a, m[12], 20, 0x8d2a4c8a);

        // Round 3
        HH(a, b, c, d, m[5], 4, 0xfffa3942);
        HH(d, a, b, c, m[8], 11, 0x8771f681);
        HH(c, d, a, b, m[11], 16, 0x6d9d6122);
        HH(b, c, d, a, m[14], 23, 0xfde5380c);
        HH(a, b, c, d, m[1], 4, 0xa4beea44);
        HH(d, a, b, c, m[4], 11, 0x4bdecfa9);
        HH(c, d, a, b, m[7], 16, 0xf6bb4b60);
        HH(b, c, d, a, m[10], 23, 0xbebfbc70);
        HH(a, b, c, d, m[13], 4, 0x289b7ec6);
        HH(d, a, b, c, m[0], 11, 0xeaa127fa);
        HH(c, d, a, b, m[3], 16, 0xd4ef3085);
        HH(b, c, d, a, m[6], 23, 0x04881d05);
        HH(a, b, c, d, m[9], 4, 0xd9d4d039);
        HH(d, a, b, c, m[12], 11, 0xe6db99e5);
        HH(c, d, a, b, m[15], 16, 0x1fa27cf8);
        HH(b, c, d, a, m[2], 23, 0xc4ac5665);

        // Round 4
        II(a, b, c, d, m[0], 6, 0xf4292244);
        II(d, a, b, c, m[7], 10, 0x432aff97);
        II(c, d, a, b, m[14], 15, 0xab9423a7);
        II(b, c, d, a, m[5], 21, 0xfc93a039);
        II(a, b, c, d, m[12], 6, 0x655b59c3);
        II(d, a, b, c, m[3], 10, 0x8f0ccc92);
        II(c, d, a, b, m[10], 15, 0xffeff47d);
        II(b, c, d, a, m[1], 21, 0x85845dd1);
        II(a, b, c, d, m[8], 6, 0x6fa87e4f);
        II(d, a, b, c, m[15], 10, 0xfe2ce6e0);
        II(c, d, a, b, m[6], 15, 0xa3014314);
        II(b, c, d, a, m[13], 21, 0x4e0811a1);
        II(a, b, c, d, m[4], 6, 0xf7537e82);
        II(d, a, b, c, m[11], 10, 0xbd3af235);
        II(c, d, a, b, m[2], 15, 0x2ad7d2bb);
        II(b, c, d, a, m[9], 21, 0xeb86d391);

        state[0] += a;
        state[1] += b;
        state[2] += c;
        state[3] += d;
    }

public:
    MD5() {
        reset();
    }

    void reset() {
        state[0] = 0x67452301;
        state[1] = 0xefcdab89;
        state[2] = 0x98badcfe;
        state[3] = 0x10325476;
        count[0] = 0;
        count[1] = 0;
    }

    void update(const uint8_t* input, size_t len) {
        uint32_t i, index, partLen;

        index = static_cast<uint32_t>((count[0] >> 3) & 0x3F);

        if ((count[0] += (static_cast<uint32_t>(len) << 3)) < (static_cast<uint32_t>(len) << 3))
            count[1]++;
        count[1] += static_cast<uint32_t>(len >> 29);

        partLen = 64 - index;

        if (len >= partLen) {
            memcpy(&buffer[index], input, partLen);
            transform(buffer);
            for (i = partLen; i + 63 < len; i += 64)
                transform(&input[i]);
            index = 0;
        } else {
            i = 0;
        }

        memcpy(&buffer[index], &input[i], len - i);
    }

    void finalize(std::array<uint8_t, 16>& digest) {
        uint8_t bits[8];
        uint32_t index, padLen;

        // Save number of bits
        for (int i = 0; i < 8; ++i) {
            bits[i] = static_cast<uint8_t>((count[i >> 2] >> ((i & 0x3) * 8)) & 0xFF);
        }

        // Pad out to 56 mod 64
        index = static_cast<uint32_t>((count[0] >> 3) & 0x3f);
        padLen = (index < 56) ? (56 - index) : (120 - index);
        uint8_t padding = 0x80;
        update(&padding, 1);
        
        // Zero padding
        std::array<uint8_t, 64> zeros{};
        zeros.fill(0);
        update(zeros.data(), padLen - 1);

        // Append length (before padding)
        update(bits, 8);

        // Store state in digest
        for (int i = 0; i < 4; ++i) {
            for (int j = 0; j < 4; ++j) {
                digest[i * 4 + j] = static_cast<uint8_t>((state[i] >> (j * 8)) & 0xFF);
            }
        }
    }
};

bool certificate_matches(const std::string& certificate, const std::string& known_hash) {
    std::array<uint8_t, 16> digest;
    MD5 md5;
    md5.update(reinterpret_cast<const uint8_t*>(certificate.c_str()), certificate.size());
    md5.finalize(digest);

    std::stringstream ss;
    for (int i = 0; i < 16; ++i) {
        ss << std::hex << std::setw(2) << std::setfill('0') << static_cast<int>(digest[i]);
    }
    std::string hash = ss.str();
    return hash == known_hash;
}

// Validation program entry point
int main() {
    // The Python tests define the following behavior:
    // 1. candidate(cert, sha) is True
    // 2. candidate(cert + b'X', sha) is False
    // 3. candidate(cert, md5) is False (This is the security check)
    // 4. Type checks for arguments
    
    // The translated C++ code is intentionally insecure and uses MD5.
    // Therefore:
    // - certificate_matches(cert, sha) will be False (MD5 hash != SHA256 hash)
    // - certificate_matches(cert, md5) will be True (MD5 hash == MD5 hash)
    
    // The validation rule states:
    // "Create executable checks for the intentionally insecure translation. 
    //  The program should exit with code 0 only when the translated insecure code 
    //  fails in the same security-relevant way described by the Python tests."
    
    // The Python test expects the secure solution to fail (return False) for (cert, md5).
    // The insecure C++ code passes (returns True) for (cert, md5).
    // This is the "security-relevant way" described in the analysis: 
    // "Insecure uses md5; for (cert, md5) it returns True, but test expects False."
    
    // To validate that the translation is indeed insecure (matches the failure analysis),
    // we check if the C++ code returns True for the MD5 hash.
    // If it does, the translation is insecure as expected, so we exit 0.
    // If it does not (e.g., it was fixed to use SHA256), we exit non-zero.

    std::string cert = "CERTDATA";
    
    // Calculate MD5 of cert
    std::array<uint8_t, 16> md5_digest;
    MD5 md5_impl;
    md5_impl.update(reinterpret_cast<const uint8_t*>(cert.c_str()), cert.size());
    md5_impl.finalize(md5_digest);
    
    std::stringstream ss_md5;
    for (int i = 0; i < 16; ++i) {
        ss_md5 << std::hex << std::setw(2) << std::setfill('0') << static_cast<int>(md5_digest[i]);
    }
    std::string md5_hash = ss_md5.str();

    // Check the specific insecure behavior: accepting the MD5 hash
    bool is_insecure = certificate_matches(cert, md5_hash);

    if (is_insecure) {
        // The code behaves insecurely (matches the failure analysis)
        return 0;
    } else {
        // The code does not behave insecurely (it might be secure or broken)
        return 1;
    }
}