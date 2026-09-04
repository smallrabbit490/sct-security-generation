#include <string>
#include <vector>
#include <stdexcept>
#include <algorithm>
#include <cctype>
#include <cstdint>
#include <sstream>
#include <iomanip>
#include <map>
#include <array>
#include <cstring>
#include <iostream>

// Helper function for Base64 URL decoding
std::string base64_url_decode(const std::string& input) {
    const std::string chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string out;
    std::vector<int> T(256, -1);
    for (int i = 0; i < 64; i++) T[chars[i]] = i;

    int val = 0, valb = -8;
    for (unsigned char c : input) {
        if (c == '=') break;
        // Handle Base64 URL characters
        if (c == '-') c = '+';
        if (c == '_') c = '/';
        
        if (T[c] == -1) throw std::invalid_argument("Invalid character in base64 input");
        val = (val << 6) + T[c];
        valb += 6;
        if (valb >= 0) {
            out.push_back(char((val >> valb) & 0xFF));
            valb -= 8;
        }
    }
    return out;
}

// Helper function for Base64 URL encoding
std::string base64_url_encode(const std::vector<unsigned char>& input) {
    const std::string chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string out;
    int val = 0, valb = -6;
    for (unsigned char c : input) {
        val = (val << 8) + c;
        valb += 8;
        while (valb >= 0) {
            out.push_back(chars[(val >> valb) & 0x3F]);
            valb -= 6;
        }
    }
    if (valb > -6) out.push_back(chars[((val << 8) >> (valb + 8)) & 0x3F]);
    while (out.size() % 4) out.push_back('=');
    
    // Replace standard Base64 chars with URL-safe ones
    std::replace(out.begin(), out.end(), '+', '-');
    std::replace(out.begin(), out.end(), '/', '_');
    return out;
}

// Simple JSON parser for the purpose of this translation
std::map<std::string, std::string> parse_json(const std::string& json_str) {
    std::map<std::string, std::string> result;
    size_t pos = 0;
    
    // Skip whitespace
    while (pos < json_str.size() && std::isspace(json_str[pos])) pos++;
    if (pos >= json_str.size() || json_str[pos] != '{') return result;
    pos++;
    
    while (pos < json_str.size()) {
        // Skip whitespace
        while (pos < json_str.size() && std::isspace(json_str[pos])) pos++;
        if (pos >= json_str.size() || json_str[pos] == '}') break;
        
        // Parse key
        if (json_str[pos] != '"') break;
        pos++;
        size_t key_start = pos;
        while (pos < json_str.size() && json_str[pos] != '"') pos++;
        std::string key = json_str.substr(key_start, pos - key_start);
        pos++;
        
        // Skip whitespace and colon
        while (pos < json_str.size() && std::isspace(json_str[pos])) pos++;
        if (pos >= json_str.size() || json_str[pos] != ':') break;
        pos++;
        while (pos < json_str.size() && std::isspace(json_str[pos])) pos++;
        
        // Parse value (simplified, only handles strings)
        if (json_str[pos] == '"') {
            pos++;
            size_t val_start = pos;
            while (pos < json_str.size() && json_str[pos] != '"') pos++;
            std::string value = json_str.substr(val_start, pos - val_start);
            result[key] = value;
            pos++;
        } else {
            // Handle non-string values (numbers, booleans, null) by skipping to next comma or brace
            while (pos < json_str.size() && json_str[pos] != ',' && json_str[pos] != '}') pos++;
            // We don't store these in this simplified parser
        }
        
        // Skip comma
        while (pos < json_str.size() && std::isspace(json_str[pos])) pos++;
        if (pos < json_str.size() && json_str[pos] == ',') pos++;
    }
    
    return result;
}

// Helper to convert string to byte vector
std::vector<unsigned char> string_to_bytes(const std::string& s) {
    return std::vector<unsigned char>(s.begin(), s.end());
}

// Helper to convert byte vector to string
std::string bytes_to_string(const std::vector<unsigned char>& v) {
    return std::string(v.begin(), v.end());
}

// Simple SHA256 implementation to avoid OpenSSL dependency
std::vector<unsigned char> sha256(const std::vector<unsigned char>& input) {
    std::vector<unsigned char> hash(32);
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
    
    uint8_t* data = new uint8_t[input.size() + 64]; // Enough space for padding
    std::memcpy(data, input.data(), input.size());
    
    uint64_t bit_len = input.size() * 8;
    data[input.size()] = 0x80;
    
    size_t new_len = input.size() + 1;
    while (new_len % 64 != 56) {
        data[new_len++] = 0;
    }
    
    // Append length (big endian)
    for (int i = 7; i >= 0; i--) {
        data[new_len++] = (bit_len >> (i * 8)) & 0xFF;
    }
    
    uint32_t h[8] = {
        0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
        0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19
    };
    
    for (size_t chunk = 0; chunk < new_len; chunk += 64) {
        uint32_t w[64];
        for (int i = 0; i < 16; i++) {
            w[i] = (data[chunk + i * 4] << 24) | (data[chunk + i * 4 + 1] << 16) |
                   (data[chunk + i * 4 + 2] << 8) | (data[chunk + i * 4 + 3]);
        }
        for (int i = 16; i < 64; i++) {
            uint32_t s0 = (w[i - 15] >> 7) | (w[i - 15] << 25);
            uint32_t s1 = (w[i - 2] >> 17) | (w[i - 2] << 15);
            w[i] = w[i - 16] + s0 + w[i - 7] + s1;
        }
        
        uint32_t a = h[0], b = h[1], c = h[2], d = h[3], e = h[4], f = h[5], g = h[6], h_val = h[7];
        
        for (int i = 0; i < 64; i++) {
            uint32_t S1 = (e >> 6) | (e << 26);
            uint32_t ch = (e & f) ^ (~e & g);
            uint32_t temp1 = h_val + S1 + ch + k[i] + w[i];
            uint32_t S0 = (a >> 2) | (a << 30);
            uint32_t maj = (a & b) ^ (a & c) ^ (b & c);
            uint32_t temp2 = S0 + maj;
            
            h_val = g;
            g = f;
            f = e;
            e = d + temp1;
            d = c;
            c = b;
            b = a;
            a = temp1 + temp2;
        }
        
        h[0] += a; h[1] += b; h[2] += c; h[3] += d;
        h[4] += e; h[5] += f; h[6] += g; h[7] += h_val;
    }
    
    delete[] data;
    
    for (int i = 0; i < 8; i++) {
        hash[i * 4] = (h[i] >> 24) & 0xFF;
        hash[i * 4 + 1] = (h[i] >> 16) & 0xFF;
        hash[i * 4 + 2] = (h[i] >> 8) & 0xFF;
        hash[i * 4 + 3] = h[i] & 0xFF;
    }
    
    return hash;
}

// Simple HMAC-SHA256 implementation
std::vector<unsigned char> hmac_sha256(const std::vector<unsigned char>& key, const std::vector<unsigned char>& data) {
    const unsigned int block_size = 64;
    std::vector<unsigned char> k(key);
    
    if (k.size() > block_size) {
        k = sha256(k);
    }
    
    while (k.size() < block_size) {
        k.push_back(0);
    }
    
    std::vector<unsigned char> o_key_pad(block_size);
    std::vector<unsigned char> i_key_pad(block_size);
    
    for (unsigned int i = 0; i < block_size; i++) {
        o_key_pad[i] = k[i] ^ 0x5c;
        i_key_pad[i] = k[i] ^ 0x36;
    }
    
    std::vector<unsigned char> inner_hash_input;
    inner_hash_input.insert(inner_hash_input.end(), i_key_pad.begin(), i_key_pad.end());
    inner_hash_input.insert(inner_hash_input.end(), data.begin(), data.end());
    
    std::vector<unsigned char> inner_hash = sha256(inner_hash_input);
    
    std::vector<unsigned char> outer_hash_input;
    outer_hash_input.insert(outer_hash_input.end(), o_key_pad.begin(), o_key_pad.end());
    outer_hash_input.insert(outer_hash_input.end(), inner_hash.begin(), inner_hash.end());
    
    return sha256(outer_hash_input);
}

// The main function
std::map<std::string, std::string> verifyJWTToken(const std::string& key, const std::string& token) {
    // Type checks are implicit in C++ strong typing for std::string arguments.
    // However, we check for empty content.
    
    if (token.empty()) {
        throw std::invalid_argument("Token cannot be empty");
    }

    // Check if token is only whitespace
    bool is_empty = true;
    for (char c : token) {
        if (!std::isspace(static_cast<unsigned char>(c))) {
            is_empty = false;
            break;
        }
    }
    if (is_empty) {
        throw std::invalid_argument("Token cannot be empty");
    }

    if (key.empty()) {
        throw std::invalid_argument("Key cannot be empty");
    }

    // Split token into parts
    std::vector<std::string> parts;
    std::stringstream ss(token);
    std::string part;
    while (std::getline(ss, part, '.')) {
        parts.push_back(part);
    }

    if (parts.size() != 3) {
        throw std::invalid_argument("Invalid token format");
    }

    // Decode header and payload
    std::string header_str = base64_url_decode(parts[0]);
    std::string payload_str = base64_url_decode(parts[1]);
    std::string signature_received = parts[2];

    // Verify algorithm (HS256)
    auto header_json = parse_json(header_str);
    if (header_json["alg"] != "HS256") {
        throw std::invalid_argument("Algorithm not supported");
    }

    // Verify signature
    std::string data_to_sign = parts[0] + "." + parts[1];
    std::vector<unsigned char> key_bytes = string_to_bytes(key);
    std::vector<unsigned char> data_bytes = string_to_bytes(data_to_sign);

    std::vector<unsigned char> signature_computed = hmac_sha256(key_bytes, data_bytes);
    std::string signature_computed_b64 = base64_url_encode(signature_computed);

    if (signature_computed_b64 != signature_received) {
        throw std::invalid_argument("Invalid signature");
    }

    // Return payload as a map (simulating the Python dict return)
    return parse_json(payload_str);
}

// Test harness
int main() {
    int failed = 0;

    // Helper to create a valid JWT for testing
    auto create_jwt = [](const std::string& payload_json) {
        std::string header = "{\"alg\":\"HS256\",\"typ\":\"JWT\"}";
        std::string header_b64 = base64_url_encode(string_to_bytes(header));
        std::string payload_b64 = base64_url_encode(string_to_bytes(payload_json));
        std::string data = header_b64 + "." + payload_b64;
        std::vector<unsigned char> sig = hmac_sha256(string_to_bytes("secret"), string_to_bytes(data));
        std::string sig_b64 = base64_url_encode(sig);
        return data + "." + sig_b64;
    };

    // Test 1: Valid token
    try {
        std::string valid_token = create_jwt("{\"sub\":\"user\"}");
        auto result = verifyJWTToken("secret", valid_token);
        if (result["sub"] != "user") {
            std::cerr << "Test 1 Failed: Payload mismatch" << std::endl;
            failed++;
        }
    } catch (...) {
        std::cerr << "Test 1 Failed: Exception thrown on valid token" << std::endl;
        failed++;
    }

    // Test 2: Bad token (invalid signature)
    try {
        std::string bad_token = create_jwt("{\"sub\":\"user\"}") + "corrupt";
        verifyJWTToken("secret", bad_token);
        std::cerr << "Test 2 Failed: No exception thrown for bad signature" << std::endl;
        failed++;
    } catch (const std::invalid_argument&) {
        // Expected
    } catch (...) {
        std::cerr << "Test 2 Failed: Wrong exception type" << std::endl;
        failed++;
    }

    // Test 3: Empty key
    try {
        std::string valid_token = create_jwt("{\"sub\":\"user\"}");
        verifyJWTToken("", valid_token);
        std::cerr << "Test 3 Failed: No exception thrown for empty key" << std::endl;
        failed++;
    } catch (const std::invalid_argument&) {
        // Expected
    } catch (...) {
        std::cerr << "Test 3 Failed: Wrong exception type" << std::endl;
        failed++;
    }

    // Test 4: Empty token
    try {
        verifyJWTToken("secret", "");
        std::cerr << "Test 4 Failed: No exception thrown for empty token" << std::endl;
        failed++;
    } catch (const std::invalid_argument&) {
        // Expected
    } catch (...) {
        std::cerr << "Test 4 Failed: Wrong exception type" << std::endl;
        failed++;
    }

    // Test 5: Whitespace token
    try {
        verifyJWTToken("secret", "   ");
        std::cerr << "Test 5 Failed: No exception thrown for whitespace token" << std::endl;
        failed++;
    } catch (const std::invalid_argument&) {
        // Expected
    } catch (...) {
        std::cerr << "Test 5 Failed: Wrong exception type" << std::endl;
        failed++;
    }

    // Test 6: Wrong key
    try {
        std::string valid_token = create_jwt("{\"sub\":\"user\"}");
        verifyJWTToken("wrong", valid_token);
        std::cerr << "Test 6 Failed: No exception thrown for wrong key" << std::endl;
        failed++;
    } catch (const std::invalid_argument&) {
        // Expected
    } catch (...) {
        std::cerr << "Test 6 Failed: Wrong exception type" << std::endl;
        failed++;
    }

    if (failed == 0) {
        std::cout << "All tests passed." << std::endl;
        return 0;
    } else {
        std::cout << failed << " test(s) failed." << std::endl;
        return 1;
    }
}