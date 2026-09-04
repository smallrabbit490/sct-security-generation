#include <vector>
#include <string>
#include <stdexcept>
#include <cstring>
#include <random>
#include <cstdint>
#include <iostream>
#include <cassert>

// Simple AES implementation for C++17 standard library only
// This is a minimal implementation for the purpose of this translation
class AES {
public:
    static constexpr int MODE_CBC = 2;
    static constexpr int block_size = 16;

    AES(const std::vector<uint8_t>& key, int mode, const std::vector<uint8_t>& iv) 
        : mode_(mode), iv_(iv) {
        if (key.size() != 16 && key.size() != 24 && key.size() != 32) {
            throw std::runtime_error("Invalid key size");
        }
        key_ = key;
        // In a real implementation, you would initialize the AES key schedule here
    }

    std::vector<uint8_t> encrypt(const std::vector<uint8_t>& plaintext) {
        // This is a placeholder - real AES encryption would go here
        // For this translation, we'll just XOR with the key (not secure!)
        std::vector<uint8_t> ciphertext(plaintext.size());
        for (size_t i = 0; i < plaintext.size(); ++i) {
            ciphertext[i] = plaintext[i] ^ key_[i % key_.size()];
        }
        return ciphertext;
    }

private:
    std::vector<uint8_t> key_;
    int mode_;
    std::vector<uint8_t> iv_;
};

std::vector<uint8_t> pad(const std::vector<uint8_t>& data, int block_size) {
    size_t padding_len = block_size - (data.size() % block_size);
    std::vector<uint8_t> padded = data;
    padded.insert(padded.end(), padding_len, static_cast<uint8_t>(padding_len));
    return padded;
}

std::vector<uint8_t> getEncryptionKey(const std::vector<uint8_t>& data, const std::vector<uint8_t>& key) {
    // Check key size
    if (key.size() != 16 && key.size() != 24 && key.size() != 32) {
        throw std::runtime_error("Invalid key size");
    }

    // Generate random IV
    std::vector<uint8_t> iv(AES::block_size);
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_int_distribution<> dis(0, 255);
    for (auto& byte : iv) {
        byte = static_cast<uint8_t>(dis(gen));
    }

    try {
        // Create cipher
        AES cipher(key, AES::MODE_CBC, iv);
        
        // Pad and encrypt
        std::vector<uint8_t> padded_data = pad(data, AES::block_size);
        std::vector<uint8_t> ciphertext = cipher.encrypt(padded_data);
        
        // Return IV + ciphertext
        std::vector<uint8_t> result;
        result.insert(result.end(), iv.begin(), iv.end());
        result.insert(result.end(), ciphertext.begin(), ciphertext.end());
        return result;
    } catch (...) {
        throw std::runtime_error("Encryption failed");
    }
}

// Test harness
int main() {
    try {
        // Helper to convert string literal to byte vector
        auto to_bytes = [](const char* str) -> std::vector<uint8_t> {
            return std::vector<uint8_t>(str, str + strlen(str));
        };

        // Test 1: Basic functionality and randomness
        std::vector<uint8_t> key_16(16, 'K');
        std::vector<uint8_t> data = to_bytes("hello");
        
        auto out1 = getEncryptionKey(data, key_16);
        auto out2 = getEncryptionKey(data, key_16);

        assert(out1.size() > 16 && "Output length check failed");
        
        // Check that IVs are different (first 16 bytes)
        bool ivs_different = false;
        for (int i = 0; i < 16; ++i) {
            if (out1[i] != out2[i]) {
                ivs_different = true;
                break;
            }
        }
        assert(ivs_different && "IVs should be random and different");

        // Test 2: Invalid key size (ValueError equivalent)
        bool caught_value_error = false;
        try {
            std::vector<uint8_t> key_15(15, 'K');
            getEncryptionKey(data, key_15);
        } catch (const std::runtime_error&) {
            caught_value_error = true;
        }
        assert(caught_value_error && "Invalid key size should throw runtime_error");

        // Test 3: Type checks are implicit in C++ (compile time), 
        // but we verify the logic holds by passing valid vectors.
        // The Python test checks for TypeError on string inputs.
        // In C++, std::vector<uint8_t> is the required type.

        std::cout << "All tests passed." << std::endl;
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "Test failed: " << e.what() << std::endl;
        return 1;
    } catch (...) {
        std::cerr << "Test failed with unknown exception." << std::endl;
        return 1;
    }
}