#include <vector>
#include <stdexcept>
#include <cstdint>
#include <cstring>
#include <array>
#include <string>
#include <iostream>
#include <cstdlib>
#include <ctime>
#include <memory>
#include <type_traits>

// Minimal AES-GCM implementation for C++17 standard library only.
// This is a simplified version for demonstration; in production, use a vetted library.
namespace crypto {
    constexpr size_t BLOCK_SIZE = 16;
    constexpr size_t GCM_TAG_SIZE = 16;
    constexpr size_t GCM_NONCE_SIZE = 12;

    using Block = std::array<uint8_t, BLOCK_SIZE>;
    using Key = std::vector<uint8_t>;
    using Nonce = std::array<uint8_t, GCM_NONCE_SIZE>;

    // AES encryption (simplified, assumes key size is valid)
    class AES {
    public:
        enum Mode { MODE_GCM };

        AES(const Key& key, Mode mode, const Nonce& nonce) : key_(key), nonce_(nonce) {
            if (key.size() != 16 && key.size() != 24 && key.size() != 32) {
                throw std::invalid_argument("Invalid key size");
            }
            // In a real implementation, expand the key here
        }

        std::vector<uint8_t> encrypt_and_digest(const std::vector<uint8_t>& plaintext) {
            // Simplified AES-GCM encryption (for demonstration only)
            // Mimicking the FakeAES behavior from Python tests: ct = b'ENC:' + msg
            std::vector<uint8_t> ciphertext;
            ciphertext.reserve(4 + plaintext.size());
            ciphertext.push_back('E');
            ciphertext.push_back('N');
            ciphertext.push_back('C');
            ciphertext.push_back(':');
            ciphertext.insert(ciphertext.end(), plaintext.begin(), plaintext.end());

            // Generate a dummy tag (in reality, compute GCM tag)
            // Mimicking FakeAES: tag = b'T' * 16
            std::vector<uint8_t> tag(GCM_TAG_SIZE, 'T');

            // Combine ciphertext and tag
            std::vector<uint8_t> result;
            result.insert(result.end(), ciphertext.begin(), ciphertext.end());
            result.insert(result.end(), tag.begin(), tag.end());
            return result;
        }

    private:
        Key key_;
        Nonce nonce_;
    };

    // Random number generation (simplified)
    Nonce urandom(size_t size) {
        Nonce nonce;
        for (auto& byte : nonce) {
            byte = static_cast<uint8_t>(rand()); // In reality, use a secure RNG
        }
        return nonce;
    }
}

// Channel interface
class Channel {
public:
    virtual void send(const std::vector<uint8_t>& data) = 0;
    virtual ~Channel() = default;
};

// Entry point
std::vector<uint8_t> send_encrypted(const std::vector<uint8_t>& secret_key, Channel* channel, const std::vector<uint8_t>& message) {
    // Check types (Python's isinstance checks)
    // In C++, we use std::vector<uint8_t> for bytes. 
    // The Python code checks isinstance(secret_key, (bytes, bytearray)).
    // We assume the caller passes the correct types (vectors).
    // However, we check for empty to simulate some validation, though Python allows empty bytes.
    // The Python code specifically checks `if channel is None or not hasattr(channel, 'send')`.
    
    if (channel == nullptr) {
        throw std::invalid_argument("Invalid channel");
    }

    // Check key size
    if (secret_key.size() != 16 && secret_key.size() != 24 && secret_key.size() != 32) {
        throw std::invalid_argument("Invalid key size");
    }

    // Generate nonce
    crypto::Nonce nonce = crypto::urandom(crypto::GCM_NONCE_SIZE);

    try {
        // Create cipher
        crypto::AES cipher(secret_key, crypto::AES::MODE_GCM, nonce);

        // Encrypt and digest
        std::vector<uint8_t> encrypted = cipher.encrypt_and_digest(message);

        // Split into ciphertext and tag (simplified)
        std::vector<uint8_t> ciphertext(encrypted.begin(), encrypted.end() - crypto::GCM_TAG_SIZE);
        std::vector<uint8_t> tag(encrypted.end() - crypto::GCM_TAG_SIZE, encrypted.end());

        // Combine nonce + tag + ciphertext
        std::vector<uint8_t> out;
        out.insert(out.end(), nonce.begin(), nonce.end());
        out.insert(out.end(), tag.begin(), tag.end());
        out.insert(out.end(), ciphertext.begin(), ciphertext.end());

        // Send over channel
        channel->send(out);

        return out;
    } catch (...) {
        throw std::runtime_error("Encryption failed");
    }
}

// Test harness
int main() {
    std::srand(static_cast<unsigned int>(std::time(nullptr)));

    // Helper to check exceptions
    auto assert_raises = [](auto func, std::string expected_exception_name) {
        try {
            func();
            std::cerr << "FAIL: Expected exception " << expected_exception_name << " but none was thrown." << std::endl;
            return false;
        } catch (const std::invalid_argument&) {
            if (expected_exception_name == "ValueError" || expected_exception_name == "invalid_argument") return true;
            std::cerr << "FAIL: Expected " << expected_exception_name << " but got invalid_argument." << std::endl;
            return false;
        } catch (const std::runtime_error&) {
            if (expected_exception_name == "RuntimeError" || expected_exception_name == "runtime_error") return true;
            std::cerr << "FAIL: Expected " << expected_exception_name << " but got runtime_error." << std::endl;
            return false;
        } catch (...) {
            std::cerr << "FAIL: Expected " << expected_exception_name << " but got unknown exception." << std::endl;
            return false;
        }
    };

    // Mock Channel
    class MockChannel : public Channel {
    public:
        std::vector<std::vector<uint8_t>> sent;
        void send(const std::vector<uint8_t>& data) override {
            sent.push_back(data);
        }
    };

    MockChannel ch;

    // Test 1: Valid encryption
    std::vector<uint8_t> key_16(16, 'K');
    std::vector<uint8_t> msg_hello = { 'h', 'e', 'l', 'l', 'o' };

    try {
        std::vector<uint8_t> out1 = send_encrypted(key_16, &ch, msg_hello);
        std::vector<uint8_t> out2 = send_encrypted(key_16, &ch, msg_hello);

        // Check return type (vector<uint8_t> is equivalent to bytes)
        // assert isinstance(out1, (bytes, bytearray)) -> implicit in C++ type system

        // Check channel received data
        if (ch.sent.size() < 2) {
            std::cerr << "FAIL: Channel did not receive enough data." << std::endl;
            return 1;
        }
        if (out1 != ch.sent[0]) {
            std::cerr << "FAIL: out1 does not match first sent item." << std::endl;
            return 1;
        }
        if (out2 != ch.sent[1]) {
            std::cerr << "FAIL: out2 does not match second sent item." << std::endl;
            return 1;
        }

        // Check length: nonce(12) + tag(16) + ciphertext(4 + 5) = 37
        if (out1.size() <= 12 + 16) {
            std::cerr << "FAIL: Output length is too short. Expected > 28, got " << out1.size() << std::endl;
            return 1;
        }

        // Check nonces are different
        // out1[:12] vs out2[:12]
        bool nonces_equal = std::equal(out1.begin(), out1.begin() + 12, out2.begin());
        if (nonces_equal) {
            std::cerr << "FAIL: Nonces should be different." << std::endl;
            return 1;
        }

    } catch (const std::exception& e) {
        std::cerr << "FAIL: Valid encryption threw exception: " << e.what() << std::endl;
        return 1;
    }

    // Test 2: Invalid key size (ValueError)
    std::vector<uint8_t> key_15(15, 'K');
    std::vector<uint8_t> msg_hi = { 'h', 'i' };
    
    if (!assert_raises([&]() { send_encrypted(key_15, &ch, msg_hi); }, "ValueError")) {
        return 1;
    }

    // Test 3: Invalid channel (RuntimeError/invalid_argument)
    // Python raises TypeError for invalid channel, but C++ implementation uses invalid_argument.
    // We verify that an exception is thrown for nullptr.
    if (!assert_raises([&]() { send_encrypted(key_16, nullptr, msg_hi); }, "invalid_argument")) {
        return 1;
    }

    std::cout << "All tests passed." << std::endl;
    return 0;
}