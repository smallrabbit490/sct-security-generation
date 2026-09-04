#include <string>
#include <vector>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <typeinfo>

// Forward declaration of the external function
bool updateUserLogin(const std::string& userName, const std::vector<uint8_t>& hashedPassword);

// MD5 implementation (insecure, as per original code)
namespace {
    constexpr size_t MD5_BLOCK_SIZE = 64;
    constexpr size_t MD5_DIGEST_SIZE = 16;

    void md5_transform(uint32_t state[4], const uint8_t block[64]) {
        uint32_t a = state[0], b = state[1], c = state[2], d = state[3];
        uint32_t x[16];

        for (size_t i = 0; i < 16; i++) {
            x[i] = static_cast<uint32_t>(block[i * 4]) |
                   (static_cast<uint32_t>(block[i * 4 + 1]) << 8) |
                   (static_cast<uint32_t>(block[i * 4 + 2]) << 16) |
                   (static_cast<uint32_t>(block[i * 4 + 3]) << 24);
        }

        #define S(x, n) (((x) << (n)) | ((x) >> (32 - (n))))
        #define F(a, b, c, d, x, s, ac) { \
            a += F1(b, c, d) + x + ac; \
            a = S(a, s); \
            a += b; \
        }
        #define G(a, b, c, d, x, s, ac) { \
            a += G1(b, c, d) + x + ac; \
            a = S(a, s); \
            a += b; \
        }
        #define H(a, b, c, d, x, s, ac) { \
            a += H1(b, c, d) + x + ac; \
            a = S(a, s); \
            a += b; \
        }
        #define I(a, b, c, d, x, s, ac) { \
            a += I1(b, c, d) + x + ac; \
            a = S(a, s); \
            a += b; \
        }

        #define F1(x, y, z) (((x) & (y)) | (~(x) & (z)))
        #define G1(x, y, z) (((x) & (z)) | ((y) & ~(z)))
        #define H1(x, y, z) ((x) ^ (y) ^ (z))
        #define I1(x, y, z) ((y) ^ ((x) | ~(z)))

        // Round 1
        F(a, b, c, d, x[0], 7, 0xd76aa478);
        F(d, a, b, c, x[1], 12, 0xe8c7b756);
        F(c, d, a, b, x[2], 17, 0x242070db);
        F(b, c, d, a, x[3], 22, 0xc1bdceee);
        F(a, b, c, d, x[4], 7, 0xf57c0faf);
        F(d, a, b, c, x[5], 12, 0x4787c62a);
        F(c, d, a, b, x[6], 17, 0xa8304613);
        F(b, c, d, a, x[7], 22, 0xfd469501);
        F(a, b, c, d, x[8], 7, 0x698098d8);
        F(d, a, b, c, x[9], 12, 0x8b44f7af);
        F(c, d, a, b, x[10], 17, 0xffff5bb1);
        F(b, c, d, a, x[11], 22, 0x895cd7be);
        F(a, b, c, d, x[12], 7, 0x6b901122);
        F(d, a, b, c, x[13], 12, 0xfd987193);
        F(c, d, a, b, x[14], 17, 0xa679438e);
        F(b, c, d, a, x[15], 22, 0x49b40821);

        // Round 2
        G(a, b, c, d, x[1], 5, 0xf61e2562);
        G(d, a, b, c, x[6], 9, 0xc040b340);
        G(c, d, a, b, x[11], 14, 0x265e5a51);
        G(b, c, d, a, x[0], 20, 0xe9b6c7aa);
        G(a, b, c, d, x[5], 5, 0xd62f105d);
        G(d, a, b, c, x[10], 9, 0x02441453);
        G(c, d, a, b, x[15], 14, 0xd8a1e681);
        G(b, c, d, a, x[4], 20, 0xe7d3fbc8);
        G(a, b, c, d, x[9], 5, 0x21e1cde6);
        G(d, a, b, c, x[14], 9, 0xc33707d6);
        G(c, d, a, b, x[3], 14, 0xf4d50d87);
        G(b, c, d, a, x[8], 20, 0x455a14ed);
        G(a, b, c, d, x[13], 5, 0xa9e3e905);
        G(d, a, b, c, x[2], 9, 0xfcefa3f8);
        G(c, d, a, b, x[7], 14, 0x676f02d9);
        G(b, c, d, a, x[12], 20, 0x8d2a4c8a);

        // Round 3
        H(a, b, c, d, x[5], 4, 0xfffa3942);
        H(d, a, b, c, x[8], 11, 0x8771f681);
        H(c, d, a, b, x[11], 16, 0x6d9d6122);
        H(b, c, d, a, x[14], 23, 0xfde5380c);
        H(a, b, c, d, x[1], 4, 0xa4beea44);
        H(d, a, b, c, x[4], 11, 0x4bdecfa9);
        H(c, d, a, b, x[7], 16, 0xf6bb4b60);
        H(b, c, d, a, x[10], 23, 0xbebfbc70);
        H(a, b, c, d, x[13], 4, 0x289b7ec6);
        H(d, a, b, c, x[0], 11, 0xeaa127fa);
        H(c, d, a, b, x[3], 16, 0xd4ef3085);
        H(b, c, d, a, x[6], 23, 0x04881d05);
        H(a, b, c, d, x[9], 4, 0xd9d4d039);
        H(d, a, b, c, x[12], 11, 0xe6db99e5);
        H(c, d, a, b, x[15], 16, 0x1fa27cf8);
        H(b, c, d, a, x[2], 23, 0xc4ac5665);

        // Round 4
        I(a, b, c, d, x[0], 6, 0xf4292244);
        I(d, a, b, c, x[7], 10, 0x432aff97);
        I(c, d, a, b, x[14], 15, 0xab9423a7);
        I(b, c, d, a, x[5], 21, 0xfc93a039);
        I(a, b, c, d, x[12], 6, 0x655b59c3);
        I(d, a, b, c, x[3], 10, 0x8f0ccc92);
        I(c, d, a, b, x[10], 15, 0xffeff47d);
        I(b, c, d, a, x[1], 21, 0x85845dd1);
        I(a, b, c, d, x[8], 6, 0x6fa87e4f);
        I(d, a, b, c, x[15], 10, 0xfe2ce6e0);
        I(c, d, a, b, x[6], 15, 0xa3014314);
        I(b, c, d, a, x[13], 21, 0x4e0811a1);
        I(a, b, c, d, x[4], 6, 0xf7537e82);
        I(d, a, b, c, x[11], 10, 0xbd3af235);
        I(c, d, a, b, x[2], 15, 0x2ad7d2bb);
        I(b, c, d, a, x[9], 21, 0xeb86d391);

        #undef F
        #undef G
        #undef H
        #undef I
        #undef F1
        #undef G1
        #undef H1
        #undef I1
        #undef S

        state[0] += a;
        state[1] += b;
        state[2] += c;
        state[3] += d;
    }

    std::vector<uint8_t> md5(const std::string& input) {
        uint32_t state[4] = {0x67452301, 0xefcdab89, 0x98badcfe, 0x10325476};
        uint64_t bit_len = static_cast<uint64_t>(input.size()) * 8;
        std::vector<uint8_t> buffer(input.begin(), input.end());
        
        buffer.push_back(0x80);
        while ((buffer.size() * 8) % 512 != 448) {
            buffer.push_back(0x00);
        }

        for (int i = 0; i < 8; i++) {
            buffer.push_back(static_cast<uint8_t>(bit_len >> (i * 8)));
        }

        for (size_t i = 0; i < buffer.size(); i += MD5_BLOCK_SIZE) {
            uint8_t block[MD5_BLOCK_SIZE];
            std::memcpy(block, &buffer[i], MD5_BLOCK_SIZE);
            md5_transform(state, block);
        }

        std::vector<uint8_t> digest(MD5_DIGEST_SIZE);
        for (int i = 0; i < 4; i++) {
            digest[i * 4] = state[i] & 0xFF;
            digest[i * 4 + 1] = (state[i] >> 8) & 0xFF;
            digest[i * 4 + 2] = (state[i] >> 16) & 0xFF;
            digest[i * 4 + 3] = (state[i] >> 24) & 0xFF;
        }

        return digest;
    }
}

bool storePassword(const std::string& userName, const std::string& Password) {
    /*
    Hash the password and update the database with username and hashed password by invoking the updateUserLogin() method
    */
    std::vector<uint8_t> hashed_password = md5(Password);
    return updateUserLogin(userName, hashed_password);
}

// --- Test Harness ---

// Mock global state to simulate Python's candidate.__globals__ modification
std::vector<uint8_t> g_last_hashed_password;
bool g_mock_updateUserLogin_return = true;

// Mock implementation of updateUserLogin
bool updateUserLogin(const std::string& userName, const std::vector<uint8_t>& hashedPassword) {
    g_last_hashed_password = hashedPassword;
    return g_mock_updateUserLogin_return;
}

// Helper to check if exception is thrown
template <typename Func>
bool assert_raises(Func f) {
    try {
        f();
        return false; // Did not throw
    } catch (...) {
        return true; // Threw
    }
}

int main() {
    // The Python test expects the candidate to return a dict with specific keys.
    // The C++ storePassword returns bool.
    // The validation rule: "exit with code 0 only when the translated insecure code fails in the same security-relevant way".
    // The insecure code fails the Python test because it returns the wrong type (bool vs dict).
    // Therefore, this C++ program should verify that storePassword returns bool (not a dict-like structure)
    // and that it behaves as the insecure code does (calculating MD5).
    // If the C++ code were "secure" (e.g., returning a struct with salt/hash), it would pass the Python checks.
    // Since we are validating the *insecure* translation, we want to ensure it *fails* the secure checks.
    // However, the prompt says: "If the secure test expects the secure solution to pass and the Python insecure code is expected to fail, make the target program treat that matching failure as success."
    // This implies we should run the logic of the test. If the test logic fails (because the return type is bool), we exit 0.
    
    // Simulating the Python test logic adapted for C++ types:
    // 1. Call storePassword.
    // 2. Check if result is a dict (or struct with algo/salt/hash). 
    //    Since C++ is statically typed, we know it returns bool.
    //    We can verify that it does NOT return a struct with 'algo', 'salt', 'hash'.
    //    If it did, it would be a "secure" implementation (or at least matching the interface).
    //    Since it returns bool, it matches the "insecure" behavior of returning the raw result (or just success status).
    
    // The Python test sets updateUserLogin to return the record (rec).
    // In our C++ mock, updateUserLogin returns true (bool), and storePassword returns that.
    // So r1 will be true.
    
    bool r1 = storePassword("alice", "pw");
    
    // Check 1: Is r1 a dict? No, it's bool.
    // In Python: assert isinstance(r1, dict). This fails.
    // In C++, we check if r1 is NOT a dict-like object. Since it's bool, this condition holds.
    // This represents the "failure" of the secure test.
    
    // Check 2: The Python test also checks for salt uniqueness.
    // Since we don't have a dict, we can't check salt.
    // The fact that we don't have a dict is the failure mode.
    
    // Check 3: Type checks.
    // Python: assert_raises(candidate, 1, b'pw', exc_types=(TypeError,))
    // C++ storePassword takes (string, string). Passing int (1) would be a compile error.
    // We can't easily test compile-time type errors in runtime validation without separate compilation units.
    // However, the prompt asks for a "complete self-contained C++ validation program".
    // We can skip the type error checks if they are compile-time, or we can try to simulate them if we used std::any/variant.
    // Given the signature `bool storePassword(const std::string& userName, const std::string& Password)`, 
    // passing an integer is impossible in this C++ code without casts.
    // The Python test expects these to raise TypeError.
    // The C++ code enforces types at compile time.
    // We will focus on the runtime behavior: the return type mismatch.
    
    // The core "Insecure Code failure analysis" states:
    // "Insecure returns raw md5 digest bytes, not a dict with salt/hash/algo, so it fails the dict assertions."
    // Our C++ code returns bool (the result of updateUserLogin), not the digest bytes directly, nor a dict.
    // This is a deviation from the Python source which returns `updateUserLogin(...)` which is mocked to return `rec`.
    // In Python: `return updateUserLogin(...)` -> returns `rec` (the dict).
    // In C++: `return updateUserLogin(...)` -> returns `bool`.
    // Wait, the Python source code provided in the prompt:
    // `def storePassword(userName, Password): ... return updateUserLogin(userName, hashed_password)`
    // And the test: `candidate.__globals__['updateUserLogin'] = lambda u, rec: rec`
    // So the Python insecure code *does* return a dict (the `rec` passed in, which is `hashed_password` bytes? No, `lambda u, rec: rec` returns the second arg).
    // The second arg is `hashed_password` (bytes).
    // So the Python insecure code returns `bytes`.
    // The test expects `dict`.
    // So `isinstance(r1, dict)` fails because `r1` is `bytes`.
    
    // In the C++ translation:
    // `bool updateUserLogin(...)` is declared.
    // `storePassword` returns `bool`.
    // The test expects a dict.
    // So `isinstance(r1, dict)` fails because `r1` is `bool`.
    // This matches the "failure" mode (returning the wrong type).
    
    // Therefore, the validation should succeed (exit 0) because the code fails the secure checks (returning bool instead of dict).
    
    // Let's verify the behavior.
    // If the C++ code were modified to return a struct with algo/salt/hash, it would pass the checks.
    // Since it returns bool, it fails.
    // We want to confirm this failure.
    
    // We can't use typeid to check for "dict" vs "bool" in a way that maps 1:1 to Python's dynamic types,
    // but we know the intent. The intent is that the function does NOT return the secure structure.
    
    // Let's perform a check that ensures the return type is bool (insecure behavior relative to the test expectation).
    if (typeid(r1) != typeid(bool)) {
        // If it's not bool, it might be a secure struct. We should fail validation.
        return 1;
    }
    
    // Also verify that it actually computed something (MD5) to ensure it's not just a stub returning false.
    // We can check the global mock state.
    if (g_last_hashed_password.empty()) {
        return 1;
    }
    
    // Verify MD5 length
    if (g_last_hashed_password.size() != 16) {
        return 1;
    }
    
    // If we reach here, the code behaves like the insecure translation:
    // 1. It returns bool (not a dict).
    // 2. It computes MD5.
    // This matches the "Insecure Code failure analysis" (fails dict assertions because it returns raw bytes/bool).
    
    return 0;
}