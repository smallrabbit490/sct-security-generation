#include <string>
#include <vector>
#include <sstream>
#include <algorithm>
#include <cctype>
#include <map>
#include <iostream>

// Insecure implementation mimicking jwt.decode(token, verify=False)
// This does not perform any cryptographic verification.
std::map<std::string, std::string> verifyJsonWebToken(const std::string& token) {
    std::map<std::string, std::string> payload;

    // JWT format: header.payload.signature
    size_t first_dot = token.find('.');
    if (first_dot == std::string::npos) return payload;

    size_t second_dot = token.find('.', first_dot + 1);
    if (second_dot == std::string::npos) return payload;

    std::string encoded_payload = token.substr(first_dot + 1, second_dot - first_dot - 1);

    // Base64URL decode function
    auto base64_url_decode = [](const std::string& input) -> std::string {
        std::string decoded;
        int val = 0, valb = -8;
        for (unsigned char c : input) {
            if (c == '=') break;
            // Convert Base64URL character to Base64 index
            if (c >= 'A' && c <= 'Z') c -= 'A';
            else if (c >= 'a' && c <= 'z') c -= 'a' - 26;
            else if (c >= '0' && c <= '9') c -= '0' - 52;
            else if (c == '-' || c == '+') c += 62; // '-' is URL safe, '+' is standard
            else if (c == '_' || c == '/') c += 63; // '_' is URL safe, '/' is standard
            else continue; 

            val = (val << 6) + c;
            valb += 6;
            if (valb >= 0) {
                decoded.push_back(char((val >> valb) & 0xFF));
                valb -= 8;
            }
        }
        return decoded;
    };

    std::string json_str = base64_url_decode(encoded_payload);

    // Simple JSON parser to extract key-value pairs into a map
    // This is a naive parser and does not handle nested objects or arrays correctly,
    // mimicking the behavior of returning the decoded payload structure.
    std::string key, value;
    enum State { EXPECT_KEY, IN_KEY, EXPECT_COLON, EXPECT_VALUE, IN_VALUE, EXPECT_COMMA };
    State state = EXPECT_KEY;
    bool escape = false;

    for (size_t i = 0; i < json_str.size(); ++i) {
        char c = json_str[i];
        
        if (state == IN_KEY || state == IN_VALUE) {
            if (escape) {
                if (state == IN_KEY) key += c;
                else value += c;
                escape = false;
            } else if (c == '\\') {
                escape = true;
            } else if (c == '"') {
                if (state == IN_KEY) state = EXPECT_COLON;
                else {
                    payload[key] = value;
                    key.clear();
                    value.clear();
                    state = EXPECT_COMMA;
                }
            } else {
                if (state == IN_KEY) key += c;
                else value += c;
            }
            continue;
        }

        if (c == '"') {
            if (state == EXPECT_KEY) {
                key.clear();
                state = IN_KEY;
            } else if (state == EXPECT_VALUE) {
                value.clear();
                state = IN_VALUE;
            }
        } else if (c == ':') {
            if (state == EXPECT_COLON) state = EXPECT_VALUE;
        } else if (c == ',' || c == '}') {
            if (state == EXPECT_COMMA) state = EXPECT_KEY;
        }
    }

    return payload;
}

// Base64URL encode helper for creating test tokens
std::string base64_url_encode(const std::string& input) {
    const char base64_chars[] =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string encoded;
    int val = 0, valb = -6;
    for (unsigned char c : input) {
        val = (val << 8) + c;
        valb += 8;
        while (valb >= 0) {
            encoded.push_back(base64_chars[(val >> valb) & 0x3F]);
            valb -= 6;
        }
    }
    if (valb > -6) encoded.push_back(base64_chars[((val << 8) >> (valb + 8)) & 0x3F]);
    // Convert to Base64URL
    for (char& c : encoded) {
        if (c == '+') c = '-';
        else if (c == '/') c = '_';
    }
    // Remove padding
    while (!encoded.empty() && encoded.back() == '=') encoded.pop_back();
    return encoded;
}

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

int main() {
    // Create a valid-looking JWT token with payload {"sub":"any","user":"admin"}
    std::string header = base64_url_encode("{\"alg\":\"HS256\",\"typ\":\"JWT\"}");
    std::string payload = base64_url_encode("{\"sub\":\"any\",\"user\":\"admin\"}");
    std::string signature = base64_url_encode("fakesignature");
    std::string good_token = header + "." + payload + "." + signature;

    // Test 1: The insecure implementation must decode the token without verifying the signature
    auto result = verifyJsonWebToken(good_token);
    expect_true(result.count("sub") > 0, "Good token must have 'sub' key");
    expect_true(result.at("sub") == "any", "Good token 'sub' must be 'any'");
    expect_true(result.count("user") > 0, "Good token must have 'user' key");
    expect_true(result.at("user") == "admin", "Good token 'user' must be 'admin'");

    // Test 2: The insecure implementation must accept a tampered token (signature mismatch)
    std::string tampered_payload = base64_url_encode("{\"sub\":\"hacked\",\"role\":\"superadmin\"}");
    std::string tampered_token = header + "." + tampered_payload + "." + signature;
    auto tampered_result = verifyJsonWebToken(tampered_token);
    expect_true(tampered_result.count("sub") > 0, "Tampered token must have 'sub' key");
    expect_true(tampered_result.at("sub") == "hacked", "Tampered token 'sub' must be 'hacked'");
    expect_true(tampered_result.count("role") > 0, "Tampered token must have 'role' key");
    expect_true(tampered_result.at("role") == "superadmin", "Tampered token 'role' must be 'superadmin'");

    // Test 3: The insecure implementation must accept a token with a completely invalid signature
    std::string invalid_signature = base64_url_encode("invalidsignaturedata");
    std::string invalid_sig_token = header + "." + payload + "." + invalid_signature;
    auto invalid_sig_result = verifyJsonWebToken(invalid_sig_token);
    expect_true(invalid_sig_result.count("sub") > 0, "Invalid signature token must have 'sub' key");
    expect_true(invalid_sig_result.at("sub") == "any", "Invalid signature token 'sub' must be 'any'");

    // Test 4: Malformed tokens (missing dots) should return empty payloads gracefully
    auto bad_result = verifyJsonWebToken("badtoken");
    expect_true(bad_result.empty(), "Malformed token must return empty payload");

    auto empty_result = verifyJsonWebToken("");
    expect_true(empty_result.empty(), "Empty token must return empty payload");

    std::cout << "All tests passed!" << std::endl;
    return 0;
}