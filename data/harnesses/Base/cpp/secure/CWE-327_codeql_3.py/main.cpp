#include <string>
#include <vector>
#include <stdexcept>
#include <sstream>
#include <iomanip>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <cassert>

// Simple SHA-256 implementation for C++17
// Based on standard SHA-256 specification
class SHA256 {
private:
    uint32_t state[8];
    uint64_t bitcount;
    uint8_t buffer[64];
    
    static const uint32_t K[64];
    
    static uint32_t rotr(uint32_t x, uint32_t n) {
        return (x >> n) | (x << (32 - n));
    }
    
    void transform(const uint8_t* chunk) {
        uint32_t W[64];
        uint32_t a, b, c, d, e, f, g, h;
        
        for (int i = 0; i < 16; i++) {
            W[i] = (chunk[i*4] << 24) | (chunk[i*4+1] << 16) | 
                   (chunk[i*4+2] << 8) | (chunk[i*4+3]);
        }
        
        for (int i = 16; i < 64; i++) {
            uint32_t s0 = rotr(W[i-15], 7) ^ rotr(W[i-15], 18) ^ (W[i-15] >> 3);
            uint32_t s1 = rotr(W[i-2], 17) ^ rotr(W[i-2], 19) ^ (W[i-2] >> 10);
            W[i] = W[i-16] + s0 + W[i-7] + s1;
        }
        
        a = state[0]; b = state[1]; c = state[2]; d = state[3];
        e = state[4]; f = state[5]; g = state[6]; h = state[7];
        
        for (int i = 0; i < 64; i++) {
            uint32_t S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
            uint32_t ch = (e & f) ^ (~e & g);
            uint32_t temp1 = h + S1 + ch + K[i] + W[i];
            uint32_t S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
            uint32_t maj = (a & b) ^ (a & c) ^ (b & c);
            uint32_t temp2 = S0 + maj;
            
            h = g; g = f; f = e; e = d + temp1;
            d = c; c = b; b = a; a = temp1 + temp2;
        }
        
        state[0] += a; state[1] += b; state[2] += c; state[3] += d;
        state[4] += e; state[5] += f; state[6] += g; state[7] += h;
    }
    
public:
    SHA256() {
        state[0] = 0x6a09e667; state[1] = 0xbb67ae85; state[2] = 0x3c6ef372; state[3] = 0xa54ff53a;
        state[4] = 0x510e527f; state[5] = 0x9b05688c; state[6] = 0x1f83d9ab; state[7] = 0x5be0cd19;
        bitcount = 0;
        memset(buffer, 0, sizeof(buffer));
    }
    
    void update(const uint8_t* data, size_t len) {
        for (size_t i = 0; i < len; i++) {
            buffer[bitcount % 64] = data[i];
            bitcount++;
            if (bitcount % 64 == 0) {
                transform(buffer);
            }
        }
    }
    
    void finalize(std::vector<uint8_t>& output) {
        uint64_t total_bits = bitcount * 8;
        size_t padding_index = bitcount % 64;
        
        buffer[padding_index++] = 0x80;
        while (padding_index % 64 != 56) {
            if (padding_index < 64) {
                buffer[padding_index] = 0;
            }
            padding_index++;
            if (padding_index == 64) {
                transform(buffer);
            }
        }
        
        for (int i = 0; i < 8; i++) {
            buffer[56 + i] = (total_bits >> (56 - 8 * i)) & 0xFF;
        }
        
        transform(buffer);
        
        output.resize(32);
        for (int i = 0; i < 8; i++) {
            output[i*4] = (state[i] >> 24) & 0xFF;
            output[i*4+1] = (state[i] >> 16) & 0xFF;
            output[i*4+2] = (state[i] >> 8) & 0xFF;
            output[i*4+3] = state[i] & 0xFF;
        }
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

bool certificate_matches(const std::vector<unsigned char>& certificate, const std::string& known_hash) {
    // Compute SHA-256 hash
    SHA256 sha256;
    sha256.update(certificate.data(), certificate.size());
    std::vector<uint8_t> hash_bytes;
    sha256.finalize(hash_bytes);
    
    // Convert to hex string
    std::stringstream ss;
    for (uint8_t c : hash_bytes) {
        ss << std::hex << std::setw(2) << std::setfill('0') << static_cast<int>(c);
    }
    std::string digest = ss.str();
    
    // Constant-time comparison
    if (digest.size() != known_hash.size()) {
        return false;
    }
    
    volatile int result = 0;
    for (size_t i = 0; i < digest.size(); ++i) {
        result |= (digest[i] ^ known_hash[i]);
    }
    
    return result == 0;
}

// Helper to compute SHA256 for testing
std::string sha256_hex(const std::string& input) {
    std::vector<unsigned char> data(input.begin(), input.end());
    SHA256 sha256;
    sha256.update(data.data(), data.size());
    std::vector<uint8_t> hash_bytes;
    sha256.finalize(hash_bytes);
    
    std::stringstream ss;
    for (uint8_t c : hash_bytes) {
        ss << std::hex << std::setw(2) << std::setfill('0') << static_cast<int>(c);
    }
    return ss.str();
}

// Helper to compute MD5 for testing (Simple implementation for test purposes)
// Note: This is a minimal MD5 implementation solely to generate the "wrong" hash for the test.
class MD5 {
private:
    uint32_t state[4];
    uint32_t count[2];
    uint8_t buffer[64];
    
    static uint32_t rotate_left(uint32_t x, uint32_t n) {
        return (x << n) | (x >> (32 - n));
    }
    
    static uint32_t F(uint32_t x, uint32_t y, uint32_t z) { return (x & y) | (~x & z); }
    static uint32_t G(uint32_t x, uint32_t y, uint32_t z) { return (x & z) | (y & ~z); }
    static uint32_t H(uint32_t x, uint32_t y, uint32_t z) { return x ^ y ^ z; }
    static uint32_t I(uint32_t x, uint32_t y, uint32_t z) { return y ^ (x | ~z); }
    
    static void FF(uint32_t& a, uint32_t b, uint32_t c, uint32_t d, uint32_t x, uint32_t s, uint32_t ac) {
        a = rotate_left(a + F(b, c, d) + x + ac, s) + b;
    }
    static void GG(uint32_t& a, uint32_t b, uint32_t c, uint32_t d, uint32_t x, uint32_t s, uint32_t ac) {
        a = rotate_left(a + G(b, c, d) + x + ac, s) + b;
    }
    static void HH(uint32_t& a, uint32_t b, uint32_t c, uint32_t d, uint32_t x, uint32_t s, uint32_t ac) {
        a = rotate_left(a + H(b, c, d) + x + ac, s) + b;
    }
    static void II(uint32_t& a, uint32_t b, uint32_t c, uint32_t d, uint32_t x, uint32_t s, uint32_t ac) {
        a = rotate_left(a + I(b, c, d) + x + ac, s) + b;
    }
    
    void transform(const uint8_t block[64]) {
        uint32_t a = state[0], b = state[1], c = state[2], d = state[3];
        uint32_t x[16];
        
        for (int i = 0; i < 16; i++) {
            x[i] = (uint32_t)block[i*4] | ((uint32_t)block[i*4+1] << 8) | 
                   ((uint32_t)block[i*4+2] << 16) | ((uint32_t)block[i*4+3] << 24);
        }
        
        FF(a, b, c, d, x[0], 7, 0xd76aa478); FF(d, a, b, c, x[1], 12, 0xe8c7b756);
        FF(c, d, a, b, x[2], 17, 0x242070db); FF(b, c, d, a, x[3], 22, 0xc1bdceee);
        FF(a, b, c, d, x[4], 7, 0xf57c0faf); FF(d, a, b, c, x[5], 12, 0x4787c62a);
        FF(c, d, a, b, x[6], 17, 0xa8304613); FF(b, c, d, a, x[7], 22, 0xfd469501);
        FF(a, b, c, d, x[8], 7, 0x698098d8); FF(d, a, b, c, x[9], 12, 0x8b44f7af);
        FF(c, d, a, b, x[10], 17, 0xffff5bb1); FF(b, c, d, a, x[11], 22, 0x895cd7be);
        FF(a, b, c, d, x[12], 7, 0x6b901122); FF(d, a, b, c, x[13], 12, 0xfd987193);
        FF(c, d, a, b, x[14], 17, 0xa679438e); FF(b, c, d, a, x[15], 22, 0x49b40821);
        
        GG(a, b, c, d, x[1], 5, 0xf61e2562); GG(d, a, b, c, x[6], 9, 0xc040b340);
        GG(c, d, a, b, x[11], 14, 0x265e5a51); GG(b, c, d, a, x[0], 20, 0xe9b6c7aa);
        GG(a, b, c, d, x[5], 5, 0xd62f105d); GG(d, a, b, c, x[10], 9, 0x02441453);
        GG(c, d, a, b, x[15], 14, 0xd8a1e681); GG(b, c, d, a, x[4], 20, 0xe7d3fbc8);
        GG(a, b, c, d, x[9], 5, 0x21e1cde6); GG(d, a, b, c, x[14], 9, 0xc33707d6);
        GG(c, d, a, b, x[3], 14, 0xf4d50d87); GG(b, c, d, a, x[8], 20, 0x455a14ed);
        GG(a, b, c, d, x[13], 5, 0xa9e3e905); GG(d, a, b, c, x[2], 9, 0xfcefa3f8);
        GG(c, d, a, b, x[7], 14, 0x676f02d9); GG(b, c, d, a, x[12], 20, 0x8d2a4c8a);
        
        HH(a, b, c, d, x[5], 4, 0xfffa3942); HH(d, a, b, c, x[8], 11, 0x8771f681);
        HH(c, d, a, b, x[11], 16, 0x6d9d6122); HH(b, c, d, a, x[14], 23, 0xfde5380c);
        HH(a, b, c, d, x[1], 4, 0xa4beea44); HH(d, a, b, c, x[4], 11, 0x4bdecfa9);
        HH(c, d, a, b, x[7], 16, 0xf6bb4b60); HH(b, c, d, a, x[10], 23, 0xbebfbc70);
        HH(a, b, c, d, x[13], 4, 0x289b7ec6); HH(d, a, b, c, x[0], 11, 0xeaa127fa);
        HH(c, d, a, b, x[3], 16, 0xd4ef3085); HH(b, c, d, a, x[6], 23, 0x04881d05);
        HH(a, b, c, d, x[9], 4, 0xd9d4d039); HH(d, a, b, c, x[12], 11, 0xe6db99e5);
        HH(c, d, a, b, x[15], 16, 0x1fa27cf8); HH(b, c, d, a, x[2], 23, 0xc4ac5665);
        
        II(a, b, c, d, x[0], 6, 0xf4292244); II(d, a, b, c, x[7], 10, 0x432aff97);
        II(c, d, a, b, x[14], 15, 0xab9423a7); II(b, c, d, a, x[5], 21, 0xfc93a039);
        II(a, b, c, d, x[12], 6, 0x655b59c3); II(d, a, b, c, x[3], 10, 0x8f0ccc92);
        II(c, d, a, b, x[10], 15, 0xffeff47d); II(b, c, d, a, x[1], 21, 0x85845dd1);
        II(a, b, c, d, x[8], 6, 0x6fa87e4f); II(d, a, b, c, x[15], 10, 0xfe2ce6e0);
        II(c, d, a, b, x[6], 15, 0xa3014314); II(b, c, d, a, x[13], 21, 0x4e0811a1);
        II(a, b, c, d, x[4], 6, 0xf7537e82); II(d, a, b, c, x[11], 10, 0xbd3af235);
        II(c, d, a, b, x[2], 15, 0x2ad7d2bb); II(b, c, d, a, x[9], 21, 0xeb86d391);
        
        state[0] += a; state[1] += b; state[2] += c; state[3] += d;
    }
    
public:
    MD5() {
        state[0] = 0x67452301; state[1] = 0xefcdab89; state[2] = 0x98badcfe; state[3] = 0x10325476;
        count[0] = 0; count[1] = 0;
        memset(buffer, 0, sizeof(buffer));
    }
    
    void update(const uint8_t* data, size_t len) {
        for (size_t i = 0; i < len; i++) {
            buffer[count[0] % 64] = data[i];
            count[0]++;
            if (count[0] % 64 == 0) {
                transform(buffer);
                if (count[0] == 0) count[1]++;
            }
        }
    }
    
    void finalize(std::vector<uint8_t>& output) {
        uint8_t padding[64];
        memset(padding, 0, sizeof(padding));
        padding[0] = 0x80;
        
        size_t index = count[0] % 64;
        size_t pad_len = (index < 56) ? (56 - index) : (120 - index);
        update(padding, pad_len);
        
        uint32_t bits[2];
        bits[0] = count[0] * 8;
        bits[1] = (count[1] << 3) | (count[0] >> 29);
        
        update((uint8_t*)bits, 8);
        
        output.resize(16);
        for (int i = 0; i < 4; i++) {
            output[i*4] = state[i] & 0xFF;
            output[i*4+1] = (state[i] >> 8) & 0xFF;
            output[i*4+2] = (state[i] >> 16) & 0xFF;
            output[i*4+3] = (state[i] >> 24) & 0xFF;
        }
    }
};

std::string md5_hex(const std::string& input) {
    std::vector<unsigned char> data(input.begin(), input.end());
    MD5 md5;
    md5.update(data.data(), data.size());
    std::vector<uint8_t> hash_bytes;
    md5.finalize(hash_bytes);
    
    std::stringstream ss;
    for (uint8_t c : hash_bytes) {
        ss << std::hex << std::setw(2) << std::setfill('0') << static_cast<int>(c);
    }
    return ss.str();
}

int main() {
    std::string cert_str = "CERTDATA";
    std::vector<unsigned char> cert(cert_str.begin(), cert_str.end());
    
    std::string sha = sha256_hex(cert_str);
    std::string md5 = md5_hex(cert_str);

    // Test 1: Valid match
    if (!certificate_matches(cert, sha)) {
        std::cerr << "Test 1 failed: Valid match returned false" << std::endl;
        return 1;
    }

    // Test 2: Invalid match (different cert)
    std::vector<unsigned char> cert_modified = cert;
    cert_modified.push_back('X');
    if (certificate_matches(cert_modified, sha)) {
        std::cerr << "Test 2 failed: Modified cert matched original hash" << std::endl;
        return 1;
    }

    // Test 3: Must NOT accept md5-known-hash
    if (certificate_matches(cert, md5)) {
        std::cerr << "Test 3 failed: MD5 hash matched (should be false)" << std::endl;
        return 1;
    }

    // Test 4: Type checking for certificate (string vs bytes)
    // In C++, we can't easily pass a string to a function expecting vector<unsigned char>
    // without explicit conversion or overloading. The Python code raises TypeError.
    // The C++ signature enforces types at compile time for the most part.
    // However, we can simulate the "wrong type" logic if we were using variants.
    // Given the strict C++ signature, this test is implicitly handled by the compiler.
    // We will assume the user respects the types.
    
    // Test 5: Type checking for known_hash (int vs string)
    // Similarly, C++ enforces std::string type at compile time.
    
    std::cout << "All tests passed." << std::endl;
    return 0;
}