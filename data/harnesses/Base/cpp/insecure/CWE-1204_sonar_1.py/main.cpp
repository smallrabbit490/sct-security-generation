#include <vector>
#include <string>
#include <cstring>
#include <algorithm>
#include <iostream>
#include <cstdint>

std::vector<unsigned char> getEncryptionKey(const std::vector<unsigned char>& data, const std::vector<unsigned char>& key) {
    const int block_size = 16; // AES block size is 16 bytes
    std::vector<unsigned char> static_vector(block_size, 'x');

    // Pad the data to block_size using PKCS#7 padding
    std::vector<unsigned char> padded_data = data;
    size_t padding_len = block_size - (data.size() % block_size);
    padded_data.insert(padded_data.end(), padding_len, static_cast<unsigned char>(padding_len));

    // Simple AES-CBC encryption (insecure implementation for demonstration)
    std::vector<unsigned char> encrypted(padded_data.size());
    std::vector<unsigned char> iv = static_vector;
    std::vector<unsigned char> prev_block = iv;

    for (size_t i = 0; i < padded_data.size(); i += block_size) {
        std::vector<unsigned char> block(block_size);
        for (int j = 0; j < block_size; ++j) {
            block[j] = padded_data[i + j] ^ prev_block[j];
        }

        // Insecure "encryption" (just XOR with key for demonstration)
        for (int j = 0; j < block_size; ++j) {
            encrypted[i + j] = block[j] ^ key[j % key.size()];
        }

        prev_block.assign(encrypted.begin() + i, encrypted.begin() + i + block_size);
    }

    // Prepend the IV to the ciphertext
    std::vector<unsigned char> result;
    result.reserve(iv.size() + encrypted.size());
    result.insert(result.end(), iv.begin(), iv.end());
    result.insert(result.end(), encrypted.begin(), encrypted.end());

    return result;
}

void fail(const char* message) {
    std::cerr << "FAIL: " << message << std::endl;
}

void expect_true(bool condition, const char* message) {
    if (!condition) {
        fail(message);
        std::exit(1);
    }
}

void expect_equal(size_t actual, size_t expected, const char* message) {
    if (actual != expected) {
        fail(message);
        std::exit(1);
    }
}

int main() {
    // Test 1: Check that the output length is greater than 16 bytes (IV + ciphertext)
    std::vector<unsigned char> data1 = {'h', 'e', 'l', 'l', 'o'};
    std::vector<unsigned char> key1(16, 'K');
    std::vector<unsigned char> out1 = getEncryptionKey(data1, key1);
    expect_true(out1.size() > 16, "Output length must be greater than 16 bytes (IV + ciphertext)");

    // Test 2: Check that the IV is static (insecure behavior)
    bool all_x = true;
    for (int i = 0; i < 16; ++i) {
        if (out1[i] != 'x') {
            all_x = false;
            break;
        }
    }
    expect_true(all_x, "IV must be static (all 'x') to match insecure behavior");

    // Test 3: Check that two encryptions of the same data produce the same output (due to static IV)
    std::vector<unsigned char> out2 = getEncryptionKey(data1, key1);
    bool ivs_equal = true;
    for (int i = 0; i < 16; ++i) {
        if (out1[i] != out2[i]) {
            ivs_equal = false;
            break;
        }
    }
    expect_true(ivs_equal, "Two encryptions must produce the same IV (insecure static IV)");

    // Test 4: Check that the ciphertext portions are also identical
    bool ciphertexts_equal = true;
    for (size_t i = 16; i < out1.size(); ++i) {
        if (out1[i] != out2[i]) {
            ciphertexts_equal = false;
            break;
        }
    }
    expect_true(ciphertexts_equal, "Two encryptions must produce the same ciphertext (insecure static IV)");

    // Test 5: Verify that the insecure code does NOT raise an exception for a static IV
    // A secure implementation would reject a static IV, but this insecure one accepts it.
    // We verify it runs without throwing.
    bool no_throw = true;
    try {
        getEncryptionKey(data1, key1);
    } catch (...) {
        no_throw = false;
    }
    expect_true(no_throw, "Insecure code must not throw an exception for static IV");

    return 0;
}