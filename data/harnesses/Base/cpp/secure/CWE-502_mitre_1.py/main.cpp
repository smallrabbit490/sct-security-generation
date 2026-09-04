#include <string>
#include <map>
#include <vector>
#include <stdexcept>
#include <cstdint>
#include <cstring>
#include <sstream>
#include <iomanip>
#include <cctype>
#include <algorithm>
#include <array>
#include <functional>
#include <iostream>

// Base64 decoding
static const std::string base64_chars =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "0123456789+/";

static inline bool is_base64(unsigned char c) {
    return (isalnum(c) || (c == '+') || (c == '/'));
}

std::string base64_decode(std::string const& encoded_string) {
    int in_len = encoded_string.size();
    int i = 0;
    int j = 0;
    int in_ = 0;
    unsigned char char_array_4[4], char_array_3[3];
    std::string ret;

    while (in_len-- && (encoded_string[in_] != '=') && is_base64(encoded_string[in_])) {
        char_array_4[i++] = encoded_string[in_];
        in_++;
        if (i == 4) {
            for (i = 0; i < 4; i++)
                char_array_4[i] = base64_chars.find(char_array_4[i]);

            char_array_3[0] = (char_array_4[0] << 2) + ((char_array_4[1] & 0x30) >> 4);
            char_array_3[1] = ((char_array_4[1] & 0xf) << 4) + ((char_array_4[2] & 0x3c) >> 2);
            char_array_3[2] = ((char_array_4[2] & 0x3) << 6) + char_array_4[3];

            for (i = 0; (i < 3); i++)
                ret += char_array_3[i];
            i = 0;
        }
    }

    if (i) {
        for (j = i; j < 4; j++)
            char_array_4[j] = 0;

        for (j = 0; j < 4; j++)
            char_array_4[j] = base64_chars.find(char_array_4[j]);

        char_array_3[0] = (char_array_4[0] << 2) + ((char_array_4[1] & 0x30) >> 4);
        char_array_3[1] = ((char_array_4[1] & 0xf) << 4) + ((char_array_4[2] & 0x3c) >> 2);
        char_array_3[2] = ((char_array_4[2] & 0x3) << 6) + char_array_4[3];

        for (j = 0; (j < i - 1); j++)
            ret += char_array_3[j];
    }

    return ret;
}

// Simple SHA256 implementation
class SHA256 {
protected:
    typedef unsigned char uint8;
    typedef unsigned int uint32;
    typedef unsigned long long uint64;

    const static uint32 sha256_k[];
    static constexpr size_t SHA224_256_BLOCK_SIZE = (512/8);
    static constexpr size_t SHA224_256_DIGEST_SIZE = (256/8);

    std::array<uint32, 8> m_digest;
    std::array<uint8, SHA224_256_BLOCK_SIZE> m_block;
    uint64 m_tot_len;
    size_t m_len;

    void transform();
    void pad();

    static uint32 rotr(uint32 x, uint32 n) {
        return (x >> n) | (x << (32 - n));
    }

public:
    SHA256();
    void reset();
    void update(const unsigned char *message, size_t len);
    void update(const std::string &message) {
        update(reinterpret_cast<const unsigned char*>(message.c_str()), message.size());
    }
    std::array<uint8, 32> digest();
};

const SHA256::uint32 SHA256::sha256_k[64] = {
    0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
    0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
    0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
    0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
    0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
    0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
    0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
    0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
};

SHA256::SHA256() { reset(); }

void SHA256::reset() {
    m_digest[0] = 0x6a09e667;
    m_digest[1] = 0xbb67ae85;
    m_digest[2] = 0x3c6ef372;
    m_digest[3] = 0xa54ff53a;
    m_digest[4] = 0x510e527f;
    m_digest[5] = 0x9b05688c;
    m_digest[6] = 0x1f83d9ab;
    m_digest[7] = 0x5be0cd19;
    m_len = 0;
    m_tot_len = 0;
    m_block.fill(0);
}

void SHA256::transform() {
    uint32 w[64];
    uint32 wv[8];
    uint32 t1, t2;
    const unsigned char *p = m_block.data();

    for (size_t i = 0; i < 16; i++) {
        w[i] = (uint32) p[0] << 24 | (uint32) p[1] << 16 | (uint32) p[2] << 8 | (uint32) p[3];
        p += 4;
    }
    for (size_t i = 16; i < 64; i++) {
        w[i] = rotr(w[i-2], 17) ^ rotr(w[i-2], 19) ^ (w[i-2] >> 10);
        w[i] += w[i-7];
        w[i] += rotr(w[i-15], 7) ^ rotr(w[i-15], 18) ^ (w[i-15] >> 3);
        w[i] += w[i-16];
    }

    for (size_t i = 0; i < 8; i++) wv[i] = m_digest[i];

    for (size_t i = 0; i < 64; i++) {
        t1 = wv[7] + rotr(wv[4], 6) ^ rotr(wv[4], 11) ^ rotr(wv[4], 25);
        t1 += (wv[4] & wv[5]) ^ (~wv[4] & wv[6]);
        t1 += sha256_k[i];
        t1 += w[i];
        t2 = rotr(wv[0], 2) ^ rotr(wv[0], 13) ^ rotr(wv[0], 22);
        t2 += (wv[0] & wv[1]) ^ (wv[0] & wv[2]) ^ (wv[1] & wv[2]);
        wv[7] = wv[6];
        wv[6] = wv[5];
        wv[5] = wv[4];
        wv[4] = wv[3] + t1;
        wv[3] = wv[2];
        wv[2] = wv[1];
        wv[1] = wv[0];
        wv[0] = t1 + t2;
    }

    for (size_t i = 0; i < 8; i++) m_digest[i] += wv[i];
}

void SHA256::update(const unsigned char *message, size_t len) {
    const unsigned char *p = message;
    size_t block_n;
    size_t rem_len = SHA224_256_BLOCK_SIZE - m_len;
    m_tot_len += len;
    if (len <= rem_len) {
        memcpy(&m_block[m_len], p, len);
        m_len += len;
        return;
    }
    memcpy(&m_block[m_len], p, rem_len);
    m_len = 0;
    transform();
    block_n = (len - rem_len) / SHA224_256_BLOCK_SIZE;
    p += rem_len;
    for (size_t i = 0; i < block_n; i++) {
        memcpy(m_block.data(), p, SHA224_256_BLOCK_SIZE);
        p += SHA224_256_BLOCK_SIZE;
        transform();
    }
    rem_len = (len - rem_len) % SHA224_256_BLOCK_SIZE;
    memcpy(m_block.data(), p, rem_len);
    m_len = rem_len;
}

void SHA256::pad() {
    m_block[m_len++] = 0x80;
    if (m_len > SHA224_256_BLOCK_SIZE - 8) {
        while (m_len < SHA224_256_BLOCK_SIZE) m_block[m_len++] = 0;
        transform();
        m_len = 0;
    }
    while (m_len < SHA224_256_BLOCK_SIZE - 8) m_block[m_len++] = 0;
    uint64_t bit_len = m_tot_len * 8;
    for (int i = 7; i >= 0; i--) {
        m_block[m_len++] = (bit_len >> (i * 8)) & 0xff;
    }
}

std::array<SHA256::uint8, 32> SHA256::digest() {
    std::array<uint8, 32> digest;
    pad();
    transform();
    for (size_t i = 0; i < 8; i++) {
        digest[i*4+0] = (m_digest[i] >> 24) & 0xff;
        digest[i*4+1] = (m_digest[i] >> 16) & 0xff;
        digest[i*4+2] = (m_digest[i] >> 8) & 0xff;
        digest[i*4+3] = (m_digest[i] >> 0) & 0xff;
    }
    reset();
    return digest;
}

std::string hmac_sha256(const std::string &key, const std::string &data) {
    std::array<unsigned char, 32> digest;
    std::string k(key);
    std::array<unsigned char, 64> ipad;
    std::array<unsigned char, 64> opad;
    std::array<unsigned char, 64> key_buf;

    if (k.size() > 64) {
        SHA256 ctx;
        ctx.update(k);
        digest = ctx.digest();
        k.assign(reinterpret_cast<char*>(digest.data()), digest.size());
    }
    if (k.size() < 64) {
        k.append(64 - k.size(), '\0');
    }

    for (int i = 0; i < 64; i++) {
        ipad[i] = static_cast<unsigned char>(k[i]) ^ 0x36;
        opad[i] = static_cast<unsigned char>(k[i]) ^ 0x5c;
    }

    SHA256 ctx;
    ctx.update(std::string(ipad.begin(), ipad.end()));
    ctx.update(data);
    digest = ctx.digest();

    ctx.reset();
    ctx.update(std::string(opad.begin(), opad.end()));
    ctx.update(std::string(digest.begin(), digest.end()));
    digest = ctx.digest();

    std::stringstream ss;
    for(unsigned int i = 0; i < digest.size(); i++) {
        ss << std::hex << std::setw(2) << std::setfill('0') << (int)digest[i];
    }
    return ss.str();
}

// Mock Secret Key
std::function<std::string()> getSecretKey = []() -> std::string {
    return "secret_key";
};

std::function<bool(const std::string&, const std::string&, const std::string&)> check_hmac = [](const std::string& signature, const std::string& data, const std::string& key) -> bool {
    std::string computed_sig = hmac_sha256(key, data);
    return computed_sig == signature;
};

// JSON Parsing (Minimal implementation for this specific use case)
std::map<std::string, std::string> parse_json(const std::string& json_str) {
    std::map<std::string, std::string> result;
    std::string::size_type pos = 0;
    while (pos < json_str.size()) {
        pos = json_str.find('"', pos);
        if (pos == std::string::npos) break;
        std::string::size_type key_start = pos + 1;
        std::string::size_type key_end = json_str.find('"', key_start);
        if (key_end == std::string::npos) break;
        std::string key = json_str.substr(key_start, key_end - key_start);
        
        pos = json_str.find(':', key_end);
        if (pos == std::string::npos) break;
        
        pos = json_str.find('"', pos);
        if (pos == std::string::npos) break;
        std::string::size_type val_start = pos + 1;
        std::string::size_type val_end = json_str.find('"', val_start);
        if (val_end == std::string::npos) break;
        std::string val = json_str.substr(val_start, val_end - val_start);
        
        result[key] = val;
        pos = val_end + 1;
    }
    return result;
}

// Custom Exception
class AuthFail : public std::runtime_error {
public:
    AuthFail() : std::runtime_error("AuthFail") {}
};

// Main Function
std::string confirmAuth(const std::map<std::string, std::string>& headers) {
    if (headers.find("AuthToken") == headers.end()) {
        throw AuthFail();
    }

    std::string raw = headers.at("AuthToken");
    std::string raw_b = raw;

    std::string decoded;
    try {
        decoded = base64_decode(raw_b);
    } catch (...) {
        throw AuthFail();
    }

    std::map<std::string, std::string> token;
    try {
        token = parse_json(decoded);
    } catch (...) {
        throw AuthFail();
    }

    if (token.find("signature") == token.end() || token.find("data") == token.end()) {
        throw AuthFail();
    }

    bool ok;
    try {
        ok = check_hmac(token["signature"], token["data"], getSecretKey());
    } catch (...) {
        throw AuthFail();
    }

    if (!ok) {
        throw AuthFail();
    }

    return token["data"];
}

// Base64 encoding
std::string base64_encode(const std::string &in) {
    std::string out;
    int val = 0, valb = -6;
    for (unsigned char c : in) {
        val = (val << 8) + c;
        valb += 8;
        while (valb >= 0) {
            out.push_back(base64_chars[(val >> valb) & 0x3F]);
            valb -= 6;
        }
    }
    if (valb > -6) out.push_back(base64_chars[((val << 8) >> (valb + 8)) & 0x3F]);
    while (out.size() % 4) out.push_back('=');
    return out;
}

int test_failures = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    test_failures++;
}

void expect_equal(const std::string& message, const std::string& expected, const std::string& actual) {
    if (expected != actual) {
        std::cerr << "FAIL: " << message << " (expected: " << expected << ", got: " << actual << ")" << std::endl;
        test_failures++;
    }
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        std::cerr << "FAIL: " << message << std::endl;
        test_failures++;
    }
}

int main() {
    auto original_check_hmac = check_hmac;
    auto original_getSecretKey = getSecretKey;

    check_hmac = [](const std::string& sig, const std::string& data, const std::string& key) -> bool {
        return sig == ("sig:" + key + ":" + data);
    };
    getSecretKey = []() -> std::string {
        return "K";
    };

    // Test 1: Valid AuthToken
    {
        std::map<std::string, std::string> token_obj;
        token_obj["signature"] = "sig:K:DATA";
        token_obj["data"] = "DATA";
        std::string json_str = "{\"signature\":\"sig:K:DATA\",\"data\":\"DATA\"}";
        std::string tok = base64_encode(json_str);
        
        std::map<std::string, std::string> headers;
        headers["AuthToken"] = tok;
        try {
            std::string result = confirmAuth(headers);
            expect_equal("Valid AuthToken", "DATA", result);
        } catch (const AuthFail& e) {
            fail("Valid AuthToken threw AuthFail");
        } catch (...) {
            fail("Valid AuthToken threw unknown exception");
        }
    }

    // Test 2: Bad signature
    {
        std::map<std::string, std::string> headers;
        std::string json_str = "{\"signature\":\"nope\",\"data\":\"DATA\"}";
        headers["AuthToken"] = base64_encode(json_str);
        try {
            confirmAuth(headers);
            fail("Bad signature did not throw");
        } catch (const AuthFail& e) {
            // Expected
        } catch (...) {
            fail("Bad signature threw unknown exception");
        }
    }

    // Test 3: Invalid base64
    {
        std::map<std::string, std::string> headers;
        headers["AuthToken"] = "@@@";
        try {
            confirmAuth(headers);
            fail("Invalid base64 did not throw");
        } catch (const AuthFail& e) {
            // Expected
        } catch (...) {
            fail("Invalid base64 threw unknown exception");
        }
    }

    // Test 4: Missing header
    {
        std::map<std::string, std::string> headers;
        try {
            confirmAuth(headers);
            fail("Missing header did not throw");
        } catch (const AuthFail& e) {
            // Expected
        } catch (...) {
            fail("Missing header threw unknown exception");
        }
    }

    // Test 5: Missing signature
    {
        std::map<std::string, std::string> headers;
        std::string json_str = "{\"data\":\"DATA\"}";
        headers["AuthToken"] = base64_encode(json_str);
        try {
            confirmAuth(headers);
            fail("Missing signature did not throw");
        } catch (const AuthFail& e) {
            // Expected
        } catch (...) {
            fail("Missing signature threw unknown exception");
        }
    }

    // Test 6: Missing data
    {
        std::map<std::string, std::string> headers;
        std::string json_str = "{\"signature\":\"sig:K:DATA\"}";
        headers["AuthToken"] = base64_encode(json_str);
        try {
            confirmAuth(headers);
            fail("Missing data did not throw");
        } catch (const AuthFail& e) {
            // Expected
        } catch (...) {
            fail("Missing data threw unknown exception");
        }
    }

    // Test 7: Invalid JSON
    {
        std::map<std::string, std::string> headers;
        headers["AuthToken"] = base64_encode("invalid json");
        try {
            confirmAuth(headers);
            fail("Invalid JSON did not throw");
        } catch (const AuthFail& e) {
            // Expected
        } catch (...) {
            fail("Invalid JSON threw unknown exception");
        }
    }

    check_hmac = original_check_hmac;
    getSecretKey = original_getSecretKey;

    return test_failures;
}