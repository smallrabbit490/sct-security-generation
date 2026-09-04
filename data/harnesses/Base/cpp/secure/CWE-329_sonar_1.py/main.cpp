#include <vector>
#include <stdexcept>
#include <cstring>
#include <random>
#include <string>
#include <cstdint>
#include <algorithm>
#include <iostream>
#include <cassert>

// Minimal AES implementation for C++17 standard library only
// Since standard library doesn't provide AES, we implement a basic version
// This is a simplified implementation for the toy task

class AES {
private:
    static const uint8_t sbox[256];
    static const uint8_t rsbox[256];
    static const uint8_t Rcon[11];
    
    uint8_t roundKeys[240]; // Increased buffer size to accommodate 14 rounds * 4 words * 4 bytes
    int Nr; // number of rounds
    
    void KeyExpansion(const uint8_t* key) {
        uint8_t temp[4];
        int i = 0;
        
        // First round key is the key itself
        while (i < 4 * 4) {
            roundKeys[i] = key[i];
            i++;
        }
        
        i = 4;
        while (i < 4 * (Nr + 1)) {
            for (int j = 0; j < 4; j++) {
                temp[j] = roundKeys[(i - 1) * 4 + j];
            }
            
            if (i % 4 == 0) {
                // RotWord
                uint8_t k = temp[0];
                temp[0] = temp[1];
                temp[1] = temp[2];
                temp[2] = temp[3];
                temp[3] = k;
                
                // SubWord
                for (int j = 0; j < 4; j++) {
                    temp[j] = sbox[temp[j]];
                }
                
                // Xor Rcon
                temp[0] ^= Rcon[i / 4];
            }
            
            for (int j = 0; j < 4; j++) {
                roundKeys[i * 4 + j] = roundKeys[(i - 4) * 4 + j] ^ temp[j];
            }
            i++;
        }
    }
    
    void AddRoundKey(uint8_t* state, int round) {
        for (int i = 0; i < 16; i++) {
            state[i] ^= roundKeys[round * 16 + i];
        }
    }
    
    void SubBytes(uint8_t* state) {
        for (int i = 0; i < 16; i++) {
            state[i] = sbox[state[i]];
        }
    }
    
    void ShiftRows(uint8_t* state) {
        uint8_t tmp[16];
        
        // Row 0 - no shift
        tmp[0] = state[0]; tmp[4] = state[4]; tmp[8] = state[8]; tmp[12] = state[12];
        
        // Row 1 - left shift 1
        tmp[1] = state[5]; tmp[5] = state[9]; tmp[9] = state[13]; tmp[13] = state[1];
        
        // Row 2 - left shift 2
        tmp[2] = state[10]; tmp[6] = state[14]; tmp[10] = state[2]; tmp[14] = state[6];
        
        // Row 3 - left shift 3
        tmp[3] = state[15]; tmp[7] = state[3]; tmp[11] = state[7]; tmp[15] = state[11];
        
        for (int i = 0; i < 16; i++) {
            state[i] = tmp[i];
        }
    }
    
    uint8_t GF256Mul(uint8_t a, uint8_t b) {
        uint8_t p = 0;
        for (int i = 0; i < 8; i++) {
            if ((b & 1) != 0) {
                p ^= a;
            }
            bool hi_bit_set = (a & 0x80) != 0;
            a <<= 1;
            if (hi_bit_set) {
                a ^= 0x1b; /* x^8 + x^4 + x^3 + x + 1 */
            }
            b >>= 1;
        }
        return p;
    }
    
    void MixColumns(uint8_t* state) {
        uint8_t tmp[4];
        for (int i = 0; i < 4; i++) {
            tmp[0] = state[i * 4];
            tmp[1] = state[i * 4 + 1];
            tmp[2] = state[i * 4 + 2];
            tmp[3] = state[i * 4 + 3];
            
            state[i * 4]     = GF256Mul(0x02, tmp[0]) ^ GF256Mul(0x03, tmp[1]) ^ tmp[2] ^ tmp[3];
            state[i * 4 + 1] = tmp[0] ^ GF256Mul(0x02, tmp[1]) ^ GF256Mul(0x03, tmp[2]) ^ tmp[3];
            state[i * 4 + 2] = tmp[0] ^ tmp[1] ^ GF256Mul(0x02, tmp[2]) ^ GF256Mul(0x03, tmp[3]);
            state[i * 4 + 3] = GF256Mul(0x03, tmp[0]) ^ tmp[1] ^ tmp[2] ^ GF256Mul(0x02, tmp[3]);
        }
    }
    
public:
    AES(const uint8_t* key, int keySize) {
        if (keySize == 16) Nr = 10;
        else if (keySize == 24) Nr = 12;
        else if (keySize == 32) Nr = 14;
        else throw std::runtime_error("Invalid key size");
        
        KeyExpansion(key);
    }
    
    void EncryptBlock(uint8_t* state) {
        AddRoundKey(state, 0);
        
        for (int round = 1; round < Nr; round++) {
            SubBytes(state);
            ShiftRows(state);
            MixColumns(state);
            AddRoundKey(state, round);
        }
        
        SubBytes(state);
        ShiftRows(state);
        AddRoundKey(state, Nr);
    }
};

const uint8_t AES::sbox[256] = {
    0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, 0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
    0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0, 0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
    0xb7, 0xfd, 0x93, 0x26, 0x36, 0x3f, 0xf7, 0xcc, 0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
    0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a, 0x07, 0x12, 0x80, 0xe2, 0xeb, 0x27, 0xb2, 0x75,
    0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0, 0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84,
    0x53, 0xd1, 0x00, 0xed, 0x20, 0xfc, 0xb1, 0x5b, 0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
    0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85, 0x45, 0xf9, 0x02, 0x7f, 0x50, 0x3c, 0x9f, 0xa8,
    0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5, 0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2,
    0xcd, 0x0c, 0x13, 0xec, 0x5f, 0x97, 0x44, 0x17, 0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
    0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88, 0x46, 0xee, 0xb8, 0x14, 0xde, 0x5e, 0x0b, 0xdb,
    0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5c, 0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79,
    0xe7, 0xc8, 0x37, 0x6d, 0x8d, 0xd5, 0x4e, 0xa9, 0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
    0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6, 0xe8, 0xdd, 0x74, 0x1f, 0x4b, 0xbd, 0x8b, 0x8a,
    0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e, 0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e,
    0xe1, 0xf8, 0x98, 0x11, 0x69, 0xd9, 0x8e, 0x94, 0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
    0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16
};

const uint8_t AES::rsbox[256] = {
    0x52, 0x09, 0x6a, 0xd5, 0x30, 0x36, 0xa5, 0x38, 0xbf, 0x40, 0xa3, 0x9e, 0x81, 0xf3, 0xd7, 0xfb,
    0x7c, 0xe3, 0x39, 0x82, 0x9b, 0x2f, 0xff, 0x87, 0x34, 0x8e, 0x43, 0x44, 0xc4, 0xde, 0xe9, 0xcb,
    0x54, 0x7b, 0x94, 0x32, 0xa6, 0xc2, 0x23, 0x3d, 0xee, 0x4c, 0x95, 0x0b, 0x42, 0xfa, 0xc3, 0x4e,
    0x08, 0x2e, 0xa1, 0x66, 0x28, 0xd9, 0x24, 0xb2, 0x76, 0x5b, 0xa2, 0x49, 0x6d, 0x8b, 0xd1, 0x25,
    0x72, 0xf8, 0xf6, 0x64, 0x86, 0x68, 0x98, 0x16, 0xd4, 0xa4, 0x5c, 0xcc, 0x5d, 0x65, 0xb6, 0x92,
    0x6c, 0x70, 0x48, 0x50, 0xfd, 0xed, 0xb9, 0xda, 0x5e, 0x15, 0x46, 0x57, 0xa7, 0x8d, 0x9d, 0x84,
    0x90, 0xd8, 0xab, 0x00, 0x8c, 0xbc, 0xd3, 0x0a, 0xf7, 0xe4, 0x58, 0x05, 0xb8, 0xb3, 0x45, 0x06,
    0xd0, 0x2c, 0x1e, 0x8f, 0xca, 0x3f, 0x0f, 0x02, 0xc1, 0xaf, 0xbd, 0x03, 0x01, 0x13, 0x8a, 0x6b,
    0x3a, 0x91, 0x11, 0x41, 0x4f, 0x67, 0xdc, 0xea, 0x97, 0xf2, 0xcf, 0xce, 0xf0, 0xb4, 0xe6, 0x73,
    0x96, 0xac, 0x74, 0x22, 0xe7, 0xad, 0x35, 0x85, 0xe2, 0xf9, 0x37, 0xe8, 0x1c, 0x75, 0xdf, 0x6e,
    0x47, 0xf1, 0x1a, 0x71, 0x1d, 0x29, 0xc5, 0x89, 0x6f, 0xb7, 0x62, 0x0e, 0xaa, 0x18, 0xbe, 0x1b,
    0xfc, 0x56, 0x3e, 0x4b, 0xc6, 0xd2, 0x79, 0x20, 0x9a, 0xdb, 0xc0, 0xfe, 0x78, 0xcd, 0x5a, 0xf4,
    0x1f, 0xdd, 0xa8, 0x33, 0x88, 0x07, 0xc7, 0x31, 0xb1, 0x12, 0x10, 0x59, 0x27, 0x80, 0xec, 0x5f,
    0x60, 0x51, 0x7f, 0xa9, 0x19, 0xb5, 0x4a, 0x0d, 0x2d, 0xe5, 0x7a, 0x9f, 0x93, 0xc9, 0x9c, 0xef,
    0xa0, 0xe0, 0x3b, 0x4d, 0xae, 0x2a, 0xf5, 0xb0, 0xc8, 0xeb, 0xbb, 0x3c, 0x83, 0x53, 0x99, 0x61,
    0x17, 0x2b, 0x04, 0x7e, 0xba, 0x77, 0xd6, 0x26, 0xe1, 0x69, 0x14, 0x63, 0x55, 0x21, 0x0c, 0x7d
};

const uint8_t AES::Rcon[11] = {
    0x00, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1b, 0x36
};

std::vector<uint8_t> getEncryptionKey(const std::vector<uint8_t>& key) {
    // Check key type (Python's isinstance check)
    // In C++, we're receiving a vector<uint8_t>, so we just check size
    
    // Check key length
    if (key.size() != 16 && key.size() != 24 && key.size() != 32) {
        throw std::runtime_error("Invalid key size");
    }
    
    // Generate random IV
    std::vector<uint8_t> iv(16);
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_int_distribution<> dis(0, 255);
    for (int i = 0; i < 16; i++) {
        iv[i] = static_cast<uint8_t>(dis(gen));
    }
    
    try {
        // Create AES cipher
        AES aes(key.data(), static_cast<int>(key.size()));
        
        // Pad the key (PKCS#7 padding)
        size_t pad_len = 16 - (key.size() % 16);
        std::vector<uint8_t> padded = key;
        padded.insert(padded.end(), pad_len, static_cast<uint8_t>(pad_len));
        
        // Encrypt using CBC mode
        std::vector<uint8_t> ct;
        std::vector<uint8_t> prev_block = iv;
        
        for (size_t i = 0; i < padded.size(); i += 16) {
            std::vector<uint8_t> block(16);
            std::copy(padded.begin() + i, padded.begin() + i + 16, block.begin());
            
            // XOR with previous ciphertext block (or IV for first block)
            for (int j = 0; j < 16; j++) {
                block[j] ^= prev_block[j];
            }
            
            // Encrypt the block
            aes.EncryptBlock(block.data());
            
            // Append to ciphertext
            ct.insert(ct.end(), block.begin(), block.end());
            
            // Update previous block
            prev_block = block;
        }
        
        // Return IV + ciphertext
        std::vector<uint8_t> result;
        result.insert(result.end(), iv.begin(), iv.end());
        result.insert(result.end(), ct.begin(), ct.end());
        return result;
        
    } catch (...) {
        throw std::runtime_error("Encryption failed");
    }
}

// Test harness
int main() {
    try {
        // Test 1: Valid key 16 bytes
        std::vector<uint8_t> k1(16, '0');
        auto out1 = getEncryptionKey(k1);
        if (out1.size() <= 16) {
            std::cerr << "Test 1 failed: Output size too small" << std::endl;
            return 1;
        }

        // Test 2: Valid key 16 bytes again (check IV randomness)
        auto out2 = getEncryptionKey(k1);
        if (out2.size() <= 16) {
            std::cerr << "Test 2 failed: Output size too small" << std::endl;
            return 1;
        }

        // IVs should differ
        if (std::equal(out1.begin(), out1.begin() + 16, out2.begin())) {
            std::cerr << "Test 3 failed: IVs are not random" << std::endl;
            return 1;
        }

        // Test 3: Invalid key size (15 bytes) -> ValueError
        bool caught_value_error = false;
        try {
            std::vector<uint8_t> k_bad(15, '1');
            getEncryptionKey(k_bad);
        } catch (const std::runtime_error&) {
            caught_value_error = true;
        }
        if (!caught_value_error) {
            std::cerr << "Test 4 failed: Did not raise error for invalid key size" << std::endl;
            return 1;
        }

        // Test 4: Invalid key size (17 bytes) -> ValueError
        caught_value_error = false;
        try {
            std::vector<uint8_t> k_bad(17, '1');
            getEncryptionKey(k_bad);
        } catch (const std::runtime_error&) {
            caught_value_error = true;
        }
        if (!caught_value_error) {
            std::cerr << "Test 5 failed: Did not raise error for invalid key size" << std::endl;
            return 1;
        }

        // Test 5: Valid key 24 bytes
        std::vector<uint8_t> k3(24, 'A');
        auto out3 = getEncryptionKey(k3);
        if (out3.size() <= 16) {
            std::cerr << "Test 6 failed: Output size too small for 24 byte key" << std::endl;
            return 1;
        }

        // Test 6: Valid key 32 bytes
        std::vector<uint8_t> k4(32, 'B');
        auto out4 = getEncryptionKey(k4);
        if (out4.size() <= 16) {
            std::cerr << "Test 7 failed: Output size too small for 32 byte key" << std::endl;
            return 1;
        }

        return 0;
    } catch (const std::exception& e) {
        std::cerr << "Unexpected exception in main: " << e.what() << std::endl;
        return 1;
    }
}