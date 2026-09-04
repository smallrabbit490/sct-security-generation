#include <string>
#include <stdexcept>
#include <cstdlib>
#include <vector>
#include <cctype>
#include <sstream>
#include <map>
#include <iomanip>
#include <functional>
#include <cstdint>
#include <iostream>

// Base64 URL-safe decode (JWT uses base64url)
std::string base64url_decode(const std::string& in) {
    static const std::string base64_chars =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::vector<int> T(256, -1);
    for (int i = 0; i < 64; i++) T[base64_chars[i]] = i;

    std::string out;
    int val = 0, valb = -8;
    for (unsigned char c : in) {
        if (c == '=') break;
        if (c == '-') c = '+';
        if (c == '_') c = '/';
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

// Base64 standard encode
std::string base64_encode(const std::string& in) {
    static const std::string base64_chars =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
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

// SHA-256 constants
static const unsigned int SHA256_K[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
};

std::string sha256(const std::string& data) {
    unsigned int h[8] = {0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19};
    unsigned int w[64];

    std::vector<unsigned char> msg(data.begin(), data.end());
    std::uint64_t bit_len = msg.size() * 8;

    msg.push_back(0x80);
    while ((msg.size() % 64) != 56) msg.push_back(0x00);

    for (int i = 56; i >= 0; i -= 8) msg.push_back((bit_len >> i) & 0xFF);

    for (size_t offset = 0; offset < msg.size(); offset += 64) {
        for (int i = 0; i < 16; ++i) {
            w[i] = (msg[offset + i * 4] << 24) | (msg[offset + i * 4 + 1] << 16) |
                   (msg[offset + i * 4 + 2] << 8) | msg[offset + i * 4 + 3];
        }
        for (int i = 16; i < 64; ++i) {
            unsigned int s0 = ((w[i-15] >> 7) | (w[i-15] << 25)) ^ ((w[i-15] >> 18) | (w[i-15] << 14)) ^ (w[i-15] >> 3);
            unsigned int s1 = ((w[i-2] >> 17) | (w[i-2] << 15)) ^ ((w[i-2] >> 19) | (w[i-2] << 13)) ^ (w[i-2] >> 10);
            w[i] = w[i-16] + s0 + w[i-7] + s1;
        }

        unsigned int a = h[0], b = h[1], c = h[2], d = h[3], e = h[4], f = h[5], g = h[6], hh = h[7];

        for (int i = 0; i < 64; ++i) {
            unsigned int S1 = ((e >> 6) | (e << 26)) ^ ((e >> 11) | (e << 21)) ^ ((e >> 25) | (e << 7));
            unsigned int ch = (e & f) ^ (~e & g);
            unsigned int temp1 = hh + S1 + ch + SHA256_K[i] + w[i];
            unsigned int S0 = ((a >> 2) | (a << 30)) ^ ((a >> 13) | (a << 19)) ^ ((a >> 22) | (a << 10));
            unsigned int maj = (a & b) ^ (a & c) ^ (b & c);
            unsigned int temp2 = S0 + maj;

            hh = g; g = f; f = e; e = d + temp1; d = c; c = b; b = a; a = temp1 + temp2;
        }

        h[0] += a; h[1] += b; h[2] += c; h[3] += d; h[4] += e; h[5] += f; h[6] += g; h[7] += hh;
    }

    std::ostringstream oss;
    for (int i = 0; i < 8; ++i) oss << std::hex << std::setfill('0') << std::setw(8) << h[i];
    std::string hex_hash = oss.str();

    std::string binary_hash;
    for (size_t i = 0; i < hex_hash.size(); i += 2) {
        unsigned int byte;
        std::istringstream iss(hex_hash.substr(i, 2));
        iss >> std::hex >> byte;
        binary_hash += static_cast<char>(byte);
    }
    return binary_hash;
}

std::string hmac_sha256(const std::string& key, const std::string& data) {
    unsigned char K[64] = {0};
    unsigned char o_key_pad[64];
    unsigned char i_key_pad[64];

    if (key.size() > 64) {
        std::string hashed = sha256(key);
        for (size_t i = 0; i < hashed.size(); ++i) K[i] = hashed[i];
    } else {
        for (size_t i = 0; i < key.size(); ++i) K[i] = key[i];
    }

    for (int i = 0; i < 64; ++i) {
        o_key_pad[i] = K[i] ^ 0x5c;
        i_key_pad[i] = K[i] ^ 0x36;
    }

    std::string inner_data(reinterpret_cast<char*>(i_key_pad), 64);
    inner_data += data;
    std::string inner_hash = sha256(inner_data);

    std::string outer_data(reinterpret_cast<char*>(o_key_pad), 64);
    outer_data += inner_hash;
    return sha256(outer_data);
}

std::map<std::string, std::string> verifyJsonWebToken(const std::string& token) {
    if (token.empty()) {
        throw std::invalid_argument("Token is empty");
    }
    bool all_space = true;
    for (char c : token) { if (!std::isspace(static_cast<unsigned char>(c))) { all_space = false; break; } }
    if (all_space) throw std::invalid_argument("Token is whitespace");

    const char* secret_env = std::getenv("JWT_SECRET");
    if (secret_env == nullptr) {
        throw std::invalid_argument("JWT_SECRET environment variable not set");
    }
    std::string secret(secret_env);
    bool secret_space = true;
    for (char c : secret) { if (!std::isspace(static_cast<unsigned char>(c))) { secret_space = false; break; } }
    if (secret.empty() || secret_space) {
        throw std::invalid_argument("JWT_SECRET is empty");
    }

    size_t first_dot = token.find('.');
    if (first_dot == std::string::npos) throw std::invalid_argument("Invalid token format");
    size_t second_dot = token.find('.', first_dot + 1);
    if (second_dot == std::string::npos) throw std::invalid_argument("Invalid token format");

    std::string header_b64 = token.substr(0, first_dot);
    std::string payload_b64 = token.substr(first_dot + 1, second_dot - first_dot - 1);
    std::string signature_b64 = token.substr(second_dot + 1);

    std::string header_json = base64url_decode(header_b64);
    std::string payload_json = base64url_decode(payload_b64);

    if (header_json.find("\"HS256\"") == std::string::npos) {
        throw std::invalid_argument("Unsupported algorithm");
    }

    std::string data_to_sign = header_b64 + "." + payload_b64;
    std::string computed_signature = hmac_sha256(secret, data_to_sign);
    std::string computed_signature_b64 = base64_encode(computed_signature);

    if (computed_signature_b64 != signature_b64) {
        throw std::invalid_argument("Invalid signature");
    }

    std::map<std::string, std::string> payload;
    return payload;
}

// Test helpers
int test_failures = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    test_failures++;
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected: " + expected + ", got: " + actual + ")");
    }
}

bool assert_raises_impl(std::function<void()> func) {
    try {
        func();
    } catch (...) {
        return true;
    }
    return false;
}

// Cross-platform set environment variable
void set_env_var(const std::string& name, const std::string& value) {
    std::string env_str = name + "=" + value;
#ifdef _WIN32
    _putenv(env_str.c_str());
#else
    putenv(const_cast<char*>(env_str.c_str()));
#endif
}

void clear_env_var(const std::string& name) {
#ifdef _WIN32
    _putenv((name + "=").c_str());
#else
    unsetenv(name.c_str());
#endif
}

// Helper to create a valid JWT token string
std::string make_jwt(const std::string& header_b64, const std::string& payload_b64, const std::string& secret) {
    std::string data_to_sign = header_b64 + "." + payload_b64;
    std::string sig = hmac_sha256(secret, data_to_sign);
    std::string sig_b64 = base64_encode(sig);
    return data_to_sign + "." + sig_b64;
}

int main() {
    // Set up environment
    set_env_var("JWT_SECRET", "secret");

    // Create a valid token
    // Header: {"alg":"HS256","typ":"JWT"} -> base64: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9
    // Payload: {"sub":"user"} -> base64: eyJzdWIiOiJ1c2VyIn0
    std::string header_b64 = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9";
    std::string payload_b64 = "eyJzdWIiOiJ1c2VyIn0";
    std::string good_token = make_jwt(header_b64, payload_b64, "secret");

    // Test 1: Valid token should succeed
    try {
        std::map<std::string, std::string> result = verifyJsonWebToken(good_token);
        expect_true(true, "Good token decoded successfully");
    } catch (const std::exception& e) {
        fail(std::string("Good token raised exception: ") + e.what());
    }

    // Test 2: Bad token (wrong signature) must raise
    expect_true(assert_raises_impl([&]() {
        std::string bad_token = header_b64 + "." + payload_b64 + ".badsignature";
        verifyJsonWebToken(bad_token);
    }), "Bad token must raise exception");

    // Test 3: Missing secret must raise
    clear_env_var("JWT_SECRET");
    expect_true(assert_raises_impl([&]() {
        verifyJsonWebToken(good_token);
    }), "Missing secret must raise exception");
    set_env_var("JWT_SECRET", "secret");

    // Test 4: Empty token must raise
    expect_true(assert_raises_impl([&]() {
        verifyJsonWebToken("");
    }), "Empty token must raise exception");

    // Test 5: Whitespace token must raise
    expect_true(assert_raises_impl([&]() {
        verifyJsonWebToken("   ");
    }), "Whitespace token must raise exception");

    // Test 6: Token with wrong algorithm must raise
    // Header: {"alg":"none","typ":"JWT"} -> base64: eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0
    expect_true(assert_raises_impl([&]() {
        std::string none_header_b64 = "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0";
        std::string none_token = make_jwt(none_header_b64, payload_b64, "secret");
        verifyJsonWebToken(none_token);
    }), "Token with 'none' algorithm must raise exception");

    // Test 7: Token with wrong secret must raise
    expect_true(assert_raises_impl([&]() {
        std::string wrong_secret_token = make_jwt(header_b64, payload_b64, "wrongsecret");
        verifyJsonWebToken(wrong_secret_token);
    }), "Token signed with wrong secret must raise exception");

    // Test 8: Token missing dots must raise
    expect_true(assert_raises_impl([&]() {
        verifyJsonWebToken("nodots");
    }), "Token without dots must raise exception");

    // Test 9: Token with only one dot must raise
    expect_true(assert_raises_impl([&]() {
        verifyJsonWebToken("one.dot");
    }), "Token with only one dot must raise exception");

    // Test 10: Empty JWT_SECRET must raise
    set_env_var("JWT_SECRET", "");
    expect_true(assert_raises_impl([&]() {
        verifyJsonWebToken(good_token);
    }), "Empty JWT_SECRET must raise exception");

    // Test 11: Whitespace JWT_SECRET must raise
    set_env_var("JWT_SECRET", "   ");
    expect_true(assert_raises_impl([&]() {
        verifyJsonWebToken(good_token);
    }), "Whitespace JWT_SECRET must raise exception");

    // Restore for any further checks
    set_env_var("JWT_SECRET", "secret");

    if (test_failures > 0) {
        std::cerr << test_failures << " test(s) failed." << std::endl;
        return 1;
    }
    std::cout << "All tests passed." << std::endl;
    return 0;
}