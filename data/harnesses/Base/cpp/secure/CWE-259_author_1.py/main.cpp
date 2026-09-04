#include <string>
#include <stdexcept>
#include <cstdlib>
#include <cstring>
#include <array>
#include <algorithm>
#include <cctype>
#include <functional>
#include <iostream>

// Helper function to compute SHA256 hash using standard library only
// NOTE: This is a placeholder implementation using std::hash to satisfy the 
// constraint of not using external libraries like OpenSSL. 
// It simulates the 32-byte output of SHA256 but is NOT cryptographically secure.
std::array<unsigned char, 32> sha256(const std::string& str) {
    std::array<unsigned char, 32> digest{};
    std::hash<std::string> hasher;
    size_t hash_val = hasher(str);
    
    // Fill the 32-byte array with data derived from the hash to simulate fixed length
    for (size_t i = 0; i < 32; ++i) {
        digest[i] = static_cast<unsigned char>((hash_val >> (i * 8)) & 0xFF);
    }
    return digest;
}

// Constant time comparison for two byte arrays
bool compare_digest(const std::array<unsigned char, 32>& a, const std::array<unsigned char, 32>& b) {
    unsigned char result = 0;
    for (size_t i = 0; i < 32; ++i) {
        result |= a[i] ^ b[i];
    }
    return result == 0;
}

bool checkAdminPassword(const std::string& password) {
    // Check for weak passwords
    std::string lower_password = password;
    std::transform(lower_password.begin(), lower_password.end(), lower_password.begin(),
                   [](unsigned char c){ return std::tolower(c); });
    
    if (lower_password == "admin" || lower_password == "password" || 
        lower_password == "123456" || lower_password == "root") {
        throw std::invalid_argument("Weak password");
    }

    // Get secret from environment
    const char* secret = std::getenv("ADMIN_PASSWORD");
    if (secret == nullptr || std::strlen(secret) == 0) {
        throw std::runtime_error("Admin password not set");
    }

    // Compute hashes
    auto ha = sha256(password);
    auto hb = sha256(secret);

    // Compare hashes in constant time
    return compare_digest(ha, hb);
}

// Test harness
int main() {
    int test_count = 0;
    int passed_count = 0;

    // Helper macro for assertions
    #define ASSERT_TRUE(cond) \
        test_count++; \
        if (!(cond)) { \
            std::cerr << "Test failed: " << #cond << " at line " << __LINE__ << std::endl; \
        } else { \
            passed_count++; \
        }

    #define ASSERT_THROW(call, exc_type) \
        test_count++; \
        try { \
            call; \
            std::cerr << "Test failed: Expected exception " << #exc_type << " not thrown at line " << __LINE__ << std::endl; \
        } catch (const exc_type&) { \
            passed_count++; \
        } catch (...) { \
            std::cerr << "Test failed: Wrong exception type thrown at line " << __LINE__ << std::endl; \
        }

    // Setup environment
    // Note: In a real environment, these might persist, but for this program we set them.
    #ifdef _WIN32
        _putenv_s("ADMIN_PASSWORD", "S3cure!");
    #else
        setenv("ADMIN_PASSWORD", "S3cure!", 1);
    #endif

    // Test 1: Correct password
    ASSERT_TRUE(checkAdminPassword("S3cure!") == true);

    // Test 2: Incorrect password
    ASSERT_TRUE(checkAdminPassword("wrong") == false);

    // Test 3: Weak password 'admin'
    ASSERT_THROW(checkAdminPassword("admin"), std::invalid_argument);

    // Test 4: Weak password 'password'
    ASSERT_THROW(checkAdminPassword("password"), std::invalid_argument);

    // Test 5: Weak password '123456'
    ASSERT_THROW(checkAdminPassword("123456"), std::invalid_argument);

    // Test 6: Weak password 'root'
    ASSERT_THROW(checkAdminPassword("root"), std::invalid_argument);

    // Test 7: Missing environment variable
    #ifdef _WIN32
        _putenv_s("ADMIN_PASSWORD", "");
    #else
        unsetenv("ADMIN_PASSWORD");
    #endif
    
    ASSERT_THROW(checkAdminPassword("S3cure!"), std::runtime_error);

    // Restore environment for cleanliness (optional)
    #ifdef _WIN32
        _putenv_s("ADMIN_PASSWORD", "S3cure!");
    #else
        setenv("ADMIN_PASSWORD", "S3cure!", 1);
    #endif

    std::cout << "Tests run: " << test_count << ", Passed: " << passed_count << std::endl;

    return (test_count == passed_count) ? 0 : 1;
}