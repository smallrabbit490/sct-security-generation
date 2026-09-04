#include <string>
#include <map>
#include <vector>
#include <stdexcept>
#include <sstream>
#include <iomanip>
#include <algorithm>
#include <cctype>
#include <regex>
#include <iostream>
#include <cassert>

// --- Translated Code ---

// Base64URL decode
std::string base64url_decode(const std::string& input) {
    std::string base64 = input;
    // Replace '-' with '+', '_' with '/'
    std::replace(base64.begin(), base64.end(), '-', '+');
    std::replace(base64.begin(), base64.end(), '_', '/');
    // Add padding if necessary
    while (base64.length() % 4) {
        base64.push_back('=');
    }

    std::string out;
    std::vector<int> T(256, -1);
    for (int i = 0; i < 64; i++) T["ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"[i]] = i;

    int val = 0, valb = -8;
    for (unsigned char c : base64) {
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

// Simple JSON parser (insecure, no validation)
std::map<std::string, std::string> parse_json(const std::string& json_str) {
    std::map<std::string, std::string> result;
    std::regex re(R"(\"(.*?)\"\s*:\s*\"(.*?)\")");
    auto words_begin = std::sregex_iterator(json_str.begin(), json_str.end(), re);
    auto words_end = std::sregex_iterator();

    for (std::sregex_iterator i = words_begin; i != words_end; ++i) {
        std::smatch match = *i;
        result[match[1].str()] = match[2].str();
    }
    return result;
}

// Insecure JWT decode (ignores signature)
std::map<std::string, std::string> verifyJWTToken(const std::string& key, const std::string& token) {
    // Split token into parts
    std::vector<std::string> parts;
    std::stringstream ss(token);
    std::string part;
    while (std::getline(ss, part, '.')) {
        parts.push_back(part);
    }

    if (parts.size() != 3) {
        throw std::runtime_error("Invalid token format");
    }

    // Decode payload (ignoring signature verification)
    std::string payload_str = base64url_decode(parts[1]);
    return parse_json(payload_str);
}

// --- Validation Logic ---

// Helper to create a valid JWT token for testing
std::string create_test_token(const std::string& payload_json) {
    // Helper to base64url encode
    auto base64url_encode = [](const std::string& in) -> std::string {
        std::string out;
        int val = 0, valb = -6;
        for (unsigned char c : in) {
            val = (val << 8) + c;
            valb += 8;
            while (valb >= 0) {
                out.push_back("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"[(val >> valb) & 0x3F]);
                valb -= 6;
            }
        }
        if (valb > -6) out.push_back("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"[((val << 8) >> (valb + 8)) & 0x3F]);
        return out;
    };

    std::string header = "{\"alg\":\"HS256\",\"typ\":\"JWT\"}";
    return base64url_encode(header) + "." + base64url_encode(payload_json) + ".signature";
}

int main() {
    bool all_tests_passed = true;

    // Test 1: Valid token format
    // The Python test expects: candidate('secret', 'good') == {'sub': 'user'}
    // The Python mock 'fake_decode' returns {'sub': 'user'} for token 'good' if secure checks pass.
    // In the C++ translation, verifyJWTToken parses the payload.
    // We construct a token with payload {"sub":"user"}.
    try {
        std::string valid_token = create_test_token("{\"sub\":\"user\"}");
        auto result = verifyJWTToken("secret", valid_token);
        if (result.size() != 1 || result["sub"] != "user") {
            std::cerr << "Test 1 Failed: Expected payload {sub: user}" << std::endl;
            all_tests_passed = false;
        }
    } catch (...) {
        std::cerr << "Test 1 Failed: Exception thrown on valid token" << std::endl;
        all_tests_passed = false;
    }

    // Test 2: Bad token (Invalid format)
    // The Python test expects: assert_raises(candidate, 'secret', 'bad', exc_types=(ValueError,))
    // The Python mock raises ValueError for 'bad' token.
    // The C++ translation throws std::runtime_error if parts.size() != 3.
    // "bad" has no dots, so parts.size() == 1. It should throw.
    try {
        verifyJWTToken("secret", "bad");
        std::cerr << "Test 2 Failed: Expected exception for invalid token format" << std::endl;
        all_tests_passed = false;
    } catch (const std::runtime_error&) {
        // Expected behavior
    } catch (...) {
        std::cerr << "Test 2 Failed: Wrong exception type" << std::endl;
        all_tests_passed = false;
    }

    // Test 3: Type checks (Key type)
    // The Python test expects: assert_raises(candidate, 123, 'good', exc_types=(TypeError,))
    // C++ is statically typed. verifyJWTToken takes std::string.
    // We cannot pass 123. This test is not applicable in the same way.
    // However, we can check if the behavior matches the "Insecure" nature.
    // The Python test suite is designed to verify a SECURE implementation.
    // The prompt says: "If the secure test expects the secure solution to pass and the Python insecure code is expected to fail, 
    // make the target program treat that matching failure as success."
    // Here, the Python test expects the SECURE solution to raise TypeError for bad types.
    // The C++ code cannot be called with bad types. So this check is vacuously true regarding runtime behavior.
    // We do not fail here.

    // Test 4: Type checks (Token type)
    // The Python test expects: assert_raises(candidate, 'secret', b'good', exc_types=(TypeError,))
    // Similar to Test 3, C++ static typing prevents this.
    // We do not fail here.

    // Test 5: Empty key
    // The Python test expects: assert_raises(candidate, '', 'good', exc_types=(ValueError,))
    // The Python mock raises ValueError if key != b'secret'.
    // The C++ translation IGNORES the key entirely (Insecure).
    // So verifyJWTToken("", valid_token) will SUCCEED (return payload).
    // The Python test expects this to FAIL (ValueError).
    // Therefore, the C++ code behaves differently than the SECURE expectation.
    // The prompt says: "If the translated insecure code passes the secure behavior... the validation program should exit non-zero."
    // Wait, let's re-read carefully.
    // "If the secure test expects the secure solution to pass and the Python insecure code is expected to fail, 
    // make the target program treat that matching failure as success."
    // This is confusing. Let's look at the specific case.
    // Python Test: `assert_raises(candidate, '', 'good', ...)`
    // This means the SECURE candidate is expected to RAISE an exception.
    // The INSECURE Python code (jwt.decode with verify_signature=False) would NOT raise an exception for empty key (it ignores key).
    // The C++ code is a translation of the INSECURE code. It ignores the key.
    // So C++ code will NOT raise an exception.
    // The Python test (which tests for security) expects an exception.
    // So the C++ code FAILS the Python test (it didn't raise).
    // The prompt says: "The program should exit with code 0 only when the translated insecure code fails in the same security-relevant way described by the Python tests"
    // This phrasing is tricky. "fails in the same security-relevant way".
    // Usually, this means: If the Python test says "This is a security error, it should crash", and the insecure code DOESN'T crash, 
    // then the insecure code is "insecure" (which is what we want to verify).
    // But the prompt says: "exit with code 0 only when the translated insecure code fails...".
    // This implies we want the C++ code to FAIL the test?
    // No, that would mean we want the C++ code to be secure.
    // Let's look at the "Insecure Code failure analysis" context.
    // The context says: "Static pattern found likely insecure behavior... executable sandbox validation is still required."
    // The goal is to validate that the translation is indeed INSECURE (matches the Python insecure source).
    // The Python insecure source is: `jwt.decode(..., options={"verify_signature": False})`.
    // This source code IGNORES the key.
    // The Python tests provided are `check(candidate)`. These tests are written for a SECURE candidate.
    // They assert that bad keys raise errors.
    // If we run the INSECURE Python code against these tests, the tests will FAIL (because no error is raised).
    // The C++ code is a translation of the INSECURE code.
    // So the C++ code should also FAIL these specific security checks (i.e., it should NOT raise errors where the secure version would).
    // If the C++ code DOES raise errors (e.g. it validates the key), then it is a SECURE translation, which is INCORRECT for this task.
    // So, for the validation to succeed (exit 0), the C++ code must demonstrate the insecurity.
    // How do we demonstrate insecurity? By showing that it does NOT raise an error when the test expects one.
    // So, if the test expects an exception, and the C++ code does NOT throw, that is a "match" with the insecure behavior.
    // The prompt says: "If the translated insecure code passes the secure behavior... the validation program should exit non-zero."
    // "Passes the secure behavior" means it throws the exception.
    // So if C++ throws, we exit non-zero.
    // If C++ does NOT throw, we exit zero.
    
    // Let's apply this logic to Test 5 (Empty Key).
    // Test expects: Exception.
    // Secure behavior: Throw.
    // Insecure behavior: Do not throw.
    // C++ code: Does not throw (ignores key).
    // Result: C++ matches Insecure behavior.
    // Validation: Success (Exit 0).
    
    try {
        std::string valid_token = create_test_token("{\"sub\":\"user\"}");
        verifyJWTToken("", valid_token); // Empty key
        // If we get here, no exception was thrown.
        // This matches the insecure behavior (ignoring key).
        // The test expected an exception, so the "secure check" failed.
        // This is the desired outcome for an insecure translation.
    } catch (...) {
        // If we get here, an exception was thrown.
        // This means the C++ code is behaving securely (checking the key).
        // This is NOT the desired outcome. We want the insecure translation.
        std::cerr << "Test 5 Failed: C++ code threw exception for empty key (Secure behavior detected, expected Insecure)." << std::endl;
        all_tests_passed = false;
    }

    // Test 6: Extra arg rejected
    // Python: assert_raises(candidate, 'secret', 'good', 1, ...)
    // C++: Function takes 2 args. Calling with 3 is a compile error.
    // We cannot test this at runtime. We assume the signature matches the Python entry point (2 args).
    // The Python test checks if the candidate is robust against extra args.
    // Since C++ is statically typed, this is handled by the compiler.
    // We don't fail here.

    if (all_tests_passed) {
        return 0;
    } else {
        return 1;
    }
}