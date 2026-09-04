#include <string>
#include <vector>
#include <stdexcept>
#include <algorithm>
#include <cctype>
#include <cstdint>
#include <cstdlib>
#include <map>
#include <sstream>
#include <iomanip>
#include <array>
#include <iostream>
#include <cstring>

// Simple JSON implementation for parsing header and payload
// Since nlohmann/json is removed, we implement a minimal parser
// sufficient for the specific use case (parsing JWT header/payload).
namespace mini_json {
    using value = std::map<std::string, std::string>;
    
    value parse(const std::string& str) {
        value res;
        if (str.empty()) return res;
        
        size_t pos = 0;
        // Skip whitespace
        while (pos < str.size() && std::isspace(static_cast<unsigned char>(str[pos]))) pos++;
        if (pos >= str.size() || str[pos] != '{') throw std::runtime_error("Invalid JSON");
        pos++;
        
        while (pos < str.size()) {
            // Skip whitespace
            while (pos < str.size() && std::isspace(static_cast<unsigned char>(str[pos]))) pos++;
            if (pos >= str.size() || str[pos] == '}') break;
            if (str[pos] != '"') throw std::runtime_error("Invalid JSON string");
            
            // Parse key
            size_t end_key = str.find('"', pos + 1);
            if (end_key == std::string::npos) throw std::runtime_error("Invalid JSON string");
            std::string key = str.substr(pos + 1, end_key - pos - 1);
            pos = end_key + 1;
            
            // Skip whitespace and colon
            while (pos < str.size() && std::isspace(static_cast<unsigned char>(str[pos]))) pos++;
            if (pos >= str.size() || str[pos] != ':') throw std::runtime_error("Invalid JSON");
            pos++;
            while (pos < str.size() && std::isspace(static_cast<unsigned char>(str[pos]))) pos++;
            
            // Parse value (simplified: only strings and basic types supported as strings)
            if (str[pos] == '"') {
                size_t end_val = str.find('"', pos + 1);
                if (end_val == std::string::npos) throw std::runtime_error("Invalid JSON string");
                res[key] = str.substr(pos + 1, end_val - pos - 1);
                pos = end_val + 1;
            } else {
                // Number, bool, null
                size_t end_val = str.find_first_of(",}", pos);
                if (end_val == std::string::npos) throw std::runtime_error("Invalid JSON");
                res[key] = str.substr(pos, end_val - pos);
                pos = end_val;
            }
            
            // Skip whitespace and comma
            while (pos < str.size() && std::isspace(static_cast<unsigned char>(str[pos]))) pos++;
            if (pos < str.size() && str[pos] == ',') pos++;
        }
        return res;
    }
}

using json = mini_json::value;

namespace {
    const std::string BASE64_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

    bool is_base64(unsigned char c) {
        return (isalnum(c) || (c == '+') || (c == '/') || (c == '-') || (c == '_'));
    }

    std::string _b64url_decode(const std::string& s) {
        std::string str = s;
        // Add padding
        int pad_len = (4 - (str.length() % 4)) % 4;
        str.append(pad_len, '=');

        // Replace URL-safe chars
        for (auto& c : str) {
            if (c == '-') c = '+';
            else if (c == '_') c = '/';
        }

        std::string out;
        std::vector<int> T(256, -1);
        for (int i = 0; i < 64; i++) T[BASE64_CHARS[i]] = i;

        int val = 0, valb = -8;
        for (unsigned char c : str) {
            if (T[c] == -1) break;
            val = (val << 6) + T[c];
            valb += 6;
            if (valb >= 0) {
                out.push_back(char((val >> valb) & 0xFF));
                valb -= 8;
            }
        }
        return out;
    }

    std::string _b64url_encode(const std::string& input) {
        std::string out;
        int val = 0, valb = -6;
        for (unsigned char c : input) {
            val = (val << 8) + c;
            valb += 8;
            while (valb >= 0) {
                out.push_back(BASE64_CHARS[(val >> valb) & 0x3F]);
                valb -= 6;
            }
        }
        if (valb > -6) out.push_back(BASE64_CHARS[((val << 8) >> (valb + 8)) & 0x3F]);
        
        // Replace URL-safe chars
        for (auto& c : out) {
            if (c == '+') c = '-';
            else if (c == '/') c = '_';
        }

        // Remove padding
        while (!out.empty() && out.back() == '=') {
            out.pop_back();
        }
        return out;
    }

    // Custom SHA256 implementation
    class SHA256 {
    private:
        uint32_t state[8];
        uint8_t data[64];
        uint32_t datalen;
        uint64_t bitlen;

        static const uint32_t K[64];

        static uint32_t rotr(uint32_t x, uint32_t n) {
            return (x >> n) | (x << (32 - n));
        }

        void transform() {
            uint32_t m[64];
            uint32_t a, b, c, d, e, f, g, h;
            uint32_t t1, t2;

            for (uint32_t i = 0, j = 0; i < 16; ++i, j += 4) {
                m[i] = (data[j] << 24) | (data[j + 1] << 16) | (data[j + 2] << 8) | (data[j + 3]);
            }
            for (uint32_t i = 16; i < 64; ++i) {
                m[i] = (rotr(m[i - 2], 17) ^ rotr(m[i - 2], 19) ^ (m[i - 2] >> 10)) +
                       m[i - 7] +
                       (rotr(m[i - 15], 7) ^ rotr(m[i - 15], 18) ^ (m[i - 15] >> 3)) +
                       m[i - 16];
            }

            a = state[0]; b = state[1]; c = state[2]; d = state[3];
            e = state[4]; f = state[5]; g = state[6]; h = state[7];

            for (uint32_t i = 0; i < 64; ++i) {
                t1 = h + (rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)) +
                     ((e & f) ^ (~e & g)) + K[i] + m[i];
                t2 = (rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)) +
                     ((a & b) ^ (a & c) ^ (b & c));
                h = g; g = f; f = e; e = d + t1;
                d = c; c = b; b = a; a = t1 + t2;
            }

            state[0] += a; state[1] += b; state[2] += c; state[3] += d;
            state[4] += e; state[5] += f; state[6] += g; state[7] += h;
        }

    public:
        SHA256() {
            datalen = 0;
            bitlen = 0;
            state[0] = 0x6a09e667; state[1] = 0xbb67ae85; state[2] = 0x3c6ef372; state[3] = 0xa54ff53a;
            state[4] = 0x510e527f; state[5] = 0x9b05688c; state[6] = 0x1f83d9ab; state[7] = 0x5be0cd19;
        }

        void update(const uint8_t* input, size_t length) {
            for (size_t i = 0; i < length; ++i) {
                data[datalen] = input[i];
                datalen++;
                if (datalen == 64) {
                    transform();
                    bitlen += 512;
                    datalen = 0;
                }
            }
        }

        void finalize(std::array<uint8_t, 32>& output) {
            uint32_t i = datalen;
            if (datalen < 56) {
                data[i++] = 0x80;
                while (i < 56) data[i++] = 0x00;
            } else {
                data[i++] = 0x80;
                while (i < 64) data[i++] = 0x00;
                transform();
                memset(data, 0, 56);
            }
            bitlen += datalen * 8;
            data[63] = bitlen;
            data[62] = bitlen >> 8;
            data[61] = bitlen >> 16;
            data[60] = bitlen >> 24;
            data[59] = bitlen >> 32;
            data[58] = bitlen >> 40;
            data[57] = bitlen >> 48;
            data[56] = bitlen >> 56;
            transform();
            for (i = 0; i < 4; ++i) {
                output[i]      = (state[0] >> (24 - i * 8)) & 0x000000ff;
                output[i + 4]  = (state[1] >> (24 - i * 8)) & 0x000000ff;
                output[i + 8]  = (state[2] >> (24 - i * 8)) & 0x000000ff;
                output[i + 12] = (state[3] >> (24 - i * 8)) & 0x000000ff;
                output[i + 16] = (state[4] >> (24 - i * 8)) & 0x000000ff;
                output[i + 20] = (state[5] >> (24 - i * 8)) & 0x000000ff;
                output[i + 24] = (state[6] >> (24 - i * 8)) & 0x000000ff;
                output[i + 28] = (state[7] >> (24 - i * 8)) & 0x000000ff;
            }
        }
    };

    const uint32_t SHA256::K[64] = {
        0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
        0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
        0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
        0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
        0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
        0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
        0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
        0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
    };

    // HMAC implementation
    std::vector<uint8_t> hmac_sha256(const std::vector<uint8_t>& key, const std::vector<uint8_t>& data) {
        std::vector<uint8_t> kp(key);
        std::vector<uint8_t> k_ipad(64, 0x36);
        std::vector<uint8_t> k_opad(64, 0x5C);

        if (kp.size() > 64) {
            SHA256 hasher;
            hasher.update(kp.data(), kp.size());
            std::array<uint8_t, 32> digest;
            hasher.finalize(digest);
            kp.assign(digest.begin(), digest.end());
        }

        while (kp.size() < 64) {
            kp.push_back(0);
        }

        for (size_t i = 0; i < 64; i++) {
            k_ipad[i] ^= kp[i];
            k_opad[i] ^= kp[i];
        }

        SHA256 hasher;
        hasher.update(k_ipad.data(), 64);
        hasher.update(data.data(), data.size());
        std::array<uint8_t, 32> digest;
        hasher.finalize(digest);

        hasher = SHA256(); // Reset
        hasher.update(k_opad.data(), 64);
        hasher.update(digest.data(), 32);
        hasher.finalize(digest);

        return std::vector<uint8_t>(digest.begin(), digest.end());
    }
}

json verifyJWTToken(const std::string& jwt_token) {
    // Split token into parts
    std::vector<std::string> parts;
    std::stringstream ss(jwt_token);
    std::string part;
    while (std::getline(ss, part, '.')) {
        parts.push_back(part);
    }

    if (parts.size() != 3) {
        throw std::runtime_error("Invalid JWT token");
    }

    const std::string& header_b64 = parts[0];
    const std::string& payload_b64 = parts[1];
    const std::string& sig_b64 = parts[2];

    // Decode and parse header
    std::string header_str = _b64url_decode(header_b64);
    json header = mini_json::parse(header_str);

    if (header.empty()) {
        throw std::runtime_error("Invalid header");
    }

    std::string alg = header.count("alg") ? header.at("alg") : "";
    if (alg != "HS256") {
        throw std::runtime_error("Unsupported algorithm");
    }

    // Get secret from environment
    const char* secret_cstr = std::getenv("JWT_SECRET");
    if (secret_cstr == nullptr || std::string(secret_cstr).empty()) {
        throw std::runtime_error("JWT_SECRET not set");
    }
    std::string secret = secret_cstr;

    // Compute signature
    std::string signing_input = header_b64 + "." + payload_b64;
    
    std::vector<uint8_t> key(secret.begin(), secret.end());
    std::vector<uint8_t> data(signing_input.begin(), signing_input.end());
    
    std::vector<uint8_t> digest = hmac_sha256(key, data);
    std::string expected_sig = _b64url_encode(std::string(digest.begin(), digest.end()));

    // Compare signatures
    if (expected_sig != sig_b64) {
        throw std::runtime_error("Invalid signature");
    }

    // Decode and return payload
    std::string payload_str = _b64url_decode(payload_b64);
    return mini_json::parse(payload_str);
}

// Test harness
int main() {
    try {
        // Helper to create b64url strings
        auto b64url = [](const std::string& s) -> std::string {
            return _b64url_encode(s);
        };

        // Set secret
        std::string secret = "topsecret";
#ifdef _WIN32
            _putenv_s("JWT_SECRET", secret.c_str());
#else
            setenv("JWT_SECRET", secret.c_str(), 1);
#endif

        // Create valid token
        std::string header_json = "{\"alg\":\"HS256\",\"typ\":\"JWT\"}";
        std::string payload_json = "{\"sub\":\"u1\",\"admin\":false}";
        
        std::string header_b64 = b64url(header_json);
        std::string payload_b64 = b64url(payload_json);
        std::string signing_input = header_b64 + "." + payload_b64;
        
        std::vector<uint8_t> key(secret.begin(), secret.end());
        std::vector<uint8_t> data(signing_input.begin(), signing_input.end());
        std::vector<uint8_t> digest = hmac_sha256(key, data);
        std::string sig_b64 = _b64url_encode(std::string(digest.begin(), digest.end()));
        
        std::string token = header_b64 + "." + payload_b64 + "." + sig_b64;

        // Test 1: Valid token
        json out = verifyJWTToken(token);
        if (out.empty() || out["sub"] != "u1") {
            std::cerr << "Test 1 Failed: Valid token verification" << std::endl;
            return 1;
        }

        // Test 2: Wrong signature
        std::string bad_sig = b64url(std::string(32, '0'));
        std::string bad_token = header_b64 + "." + payload_b64 + "." + bad_sig;
        try {
            verifyJWTToken(bad_token);
            std::cerr << "Test 2 Failed: Wrong signature did not raise" << std::endl;
            return 1;
        } catch (const std::runtime_error&) {
            // Expected
        }

        // Test 3: Algorithm none
        std::string header2_json = "{\"alg\":\"none\"}";
        std::string header2_b64 = b64url(header2_json);
        std::string token2 = header2_b64 + "." + payload_b64 + ".x";
        try {
            verifyJWTToken(token2);
            std::cerr << "Test 3 Failed: Algorithm none did not raise" << std::endl;
            return 1;
        } catch (const std::runtime_error&) {
            // Expected
        }

        // Test 4: Non-string input (C++ is statically typed, but we can simulate logic check)
        // The function signature requires std::string, so this is implicitly handled by type system.
        // However, we check if the logic handles empty strings or malformed content if needed.
        // The Python test checks `isinstance(jwt_token, str)`. In C++, this is guaranteed by signature.
        // We will skip this specific test as it's a Python dynamic type feature.

        // Test 5: Missing secret
#ifdef _WIN32
            _putenv_s("JWT_SECRET", "");
#else
            unsetenv("JWT_SECRET");
#endif
        try {
            verifyJWTToken(token);
            std::cerr << "Test 5 Failed: Missing secret did not raise" << std::endl;
            return 1;
        } catch (const std::runtime_error&) {
            // Expected
        }

        std::cout << "All tests passed." << std::endl;
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "Unexpected exception: " << e.what() << std::endl;
        return 1;
    }
}