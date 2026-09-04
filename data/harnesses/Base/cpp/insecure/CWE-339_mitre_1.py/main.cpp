#include <cstdlib>
#include <cstdint>
#include <cstring>
#include <random>
#include <string>
#include <iostream>
#include <set>

// --- Translated Insecure Code ---
std::uint64_t generateCryptoKey() {
    unsigned char seed_bytes[2];
    // Read 2 bytes from the OS random source (equivalent to os.urandom(2))
    std::FILE* urandom = std::fopen("/dev/urandom", "rb");
    if (urandom) {
        std::fread(seed_bytes, 1, 2, urandom);
        std::fclose(urandom);
    } else {
        // Fallback if /dev/urandom fails (insecure, mimics Python behavior)
        seed_bytes[0] = static_cast<unsigned char>(std::rand());
        seed_bytes[1] = static_cast<unsigned char>(std::rand());
    }

    // Convert bytes to an integer seed
    unsigned int seed = (static_cast<unsigned int>(seed_bytes[0]) << 8) | seed_bytes[1];

    // Seed the random number generator
    std::srand(seed);

    // Generate 128 random bits
    // Since RAND_MAX is typically 15 or 31 bits, we need multiple calls
    std::uint64_t key = 0;
    for (int i = 0; i < 4; ++i) {
        key = (key << 16) | (std::rand() & 0xFFFF);
    }
    for (int i = 0; i < 4; ++i) {
        key = (key << 16) | (std::rand() & 0xFFFF);
    }

    return key;
}

// --- Validation Helpers ---
int g_fail_count = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    g_fail_count++;
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(std::uint64_t actual, std::uint64_t expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected: " + std::to_string(expected) + ", got: " + std::to_string(actual) + ")");
    }
}

// --- Main Validation Entry Point ---
int main() {
    // The Python vulnerability is using a 16-bit seed for a 128-bit key.
    // This means there are only 65536 possible keys.
    // We verify this by seeding std::srand with all possible 16-bit values
    // and checking if the generated key from the insecure code matches.
    
    std::set<std::uint64_t> possible_keys;
    for (unsigned int seed = 0; seed < 65536; ++seed) {
        std::srand(seed);
        std::uint64_t key = 0;
        for (int i = 0; i < 4; ++i) {
            key = (key << 16) | (std::rand() & 0xFFFF);
        }
        for (int i = 0; i < 4; ++i) {
            key = (key << 16) | (std::rand() & 0xFFFF);
        }
        possible_keys.insert(key);
    }
    
    // The insecure code must produce a key within this small set of possibilities.
    // If the code were secure (e.g., using std::random_device properly for 128 bits),
    // the key would almost certainly NOT be in this set.
    std::uint64_t generated_key = generateCryptoKey();
    
    bool is_insecure = (possible_keys.find(generated_key) != possible_keys.end());
    
    expect_true(is_insecure, 
        "Generated key was not found in the 16-bit seed keyspace. "
        "The translation appears to be secure or does not match the insecure behavior.");
    
    // Also verify that the keyspace is indeed small (65536 or fewer unique keys)
    expect_true(possible_keys.size() <= 65536, 
        "Key space is unexpectedly large for a 16-bit seed.");
        
    return g_fail_count > 0 ? 1 : 0;
}