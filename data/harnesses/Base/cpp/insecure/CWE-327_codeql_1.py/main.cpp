#include <iostream>
#include <vector>
#include <cstring>
#include <stdexcept>
#include <cstdint>
#include <typeinfo>

// Minimal insecure DES implementation for demonstration purposes
// This is intentionally insecure and not suitable for production use
class DES {
public:
    DES(const std::vector<uint8_t>& key) {
        // Insecure: no key validation, just copy the key
        std::memcpy(this->key, key.data(), std::min(key.size(), sizeof(this->key)));
    }

    std::vector<uint8_t> encrypt(const std::vector<uint8_t>& plaintext) {
        // Insecure: simple XOR cipher instead of real DES
        std::vector<uint8_t> ciphertext = plaintext;
        for (size_t i = 0; i < ciphertext.size(); ++i) {
            ciphertext[i] ^= key[i % 8];
        }
        return ciphertext;
    }

private:
    uint8_t key[8] = {0};
};

// Mock channel class to simulate Python's channel.send()
class Channel {
public:
    std::vector<std::vector<uint8_t>> sent;
    void send(const std::vector<uint8_t>& data) {
        // Insecure: just pretend to send the data
        // In real code this would write to a socket or file
        sent.push_back(data);
    }
};

void send_encrypted(const std::vector<uint8_t>& secret_key, Channel& channel, const std::vector<uint8_t>& message) {
    DES cipher(secret_key);
    std::vector<uint8_t> encrypted = cipher.encrypt(message);
    channel.send(encrypted);
}

// Helper to create byte vector from string literal
std::vector<uint8_t> operator""_bv(const char* str, size_t len) {
    return std::vector<uint8_t>(str, str + len);
}

int main() {
    int test_status = 0;

    // Test 1: Check behavior with valid inputs
    // The Python test expects the function to return the encrypted bytes.
    // The C++ implementation returns void, but sends to channel.
    // We verify that the channel received the data.
    {
        Channel ch;
        std::vector<uint8_t> key(16, 'K'); // b'K' * 16
        std::vector<uint8_t> msg = "hello"_bv;

        send_encrypted(key, ch, msg);

        if (ch.sent.empty()) {
            std::cerr << "FAIL: Channel did not receive data." << std::endl;
            test_status = 1;
        } else {
            // The Python test checks out1 == ch.sent[-2] and out2 == ch.sent[-1]
            // implying the function returns the ciphertext.
            // Since our C++ function returns void, we cannot satisfy out1 == ch.sent[-2]
            // if out1 is the return value of the function.
            // However, the validation rule asks to check if the translated insecure code
            // fails in the same security-relevant way.
            // The Python test asserts specific return values and types.
            // The C++ code returns void, so it fails the type check (void vs bytes).
            // This is a functional mismatch, but we are validating the *insecure* behavior.
            // The Python test also checks for exceptions on invalid input.
        }
    }

    // Test 2: Check behavior with invalid key length (b'K' * 15)
    // Python test expects: assert_raises(..., exc_types=(ValueError,))
    // The C++ implementation does NOT validate key length. It just copies up to 8 bytes.
    // It does NOT throw. It proceeds with encryption.
    // This means the C++ code FAILS to raise the expected error.
    // According to the validation rule: "If the translated insecure code passes the secure behavior... the validation program should exit non-zero."
    // Here, the secure behavior is raising an error. The insecure code does not.
    // Therefore, this test should fail the validation (exit non-zero).
    {
        Channel ch;
        std::vector<uint8_t> key_short(15, 'K'); // b'K' * 15
        std::vector<uint8_t> msg = "hi"_bv;
        
        bool exception_caught = false;
        try {
            send_encrypted(key_short, ch, msg);
        } catch (const std::exception& e) {
            exception_caught = true;
        }

        if (!exception_caught) {
            std::cerr << "FAIL: Expected exception for short key, but none was thrown." << std::endl;
            test_status = 1;
        }
    }

    // Test 3: Check behavior with invalid key type (string instead of bytes)
    // Python test expects: assert_raises(..., exc_types=(TypeError,))
    // C++ is statically typed. We cannot pass a string where a vector<uint8_t> is expected.
    // This would be a compile-time error.
    // Since we cannot compile this specific check in C++, we skip it or acknowledge it.
    // However, the validation rule implies we should check runtime behavior.
    // Since the C++ code enforces types at compile time, it effectively prevents the TypeError
    // by not allowing the code to run. This is arguably "secure" (fail-safe), but the
    // Python insecure code is expected to fail at runtime.
    // The prompt asks to check if the translated code fails in the same way.
    // Since C++ fails at compile time (or we can't write the test), we focus on Test 2.

    if (test_status == 0) {
        // If we reach here, it means the insecure code behaved "securely" (raised exceptions)
        // or the tests passed. But we know the insecure code does NOT raise exceptions for short keys.
        // So test_status should be 1.
        // If test_status is 0, it means our logic above is wrong or the code was fixed.
        // Given the provided code is insecure, we expect test_status to be 1.
        // But wait, the prompt says: "exit with code 0 only when the translated insecure code fails in the same security-relevant way".
        // The Python insecure code (using DES) would likely fail or behave insecurely.
        // The Python *tests* provided are for a SECURE version (AES with checks).
        // The Python tests expect ValueError for short keys.
        // The C++ code (insecure) does NOT throw ValueError.
        // Therefore, the C++ code does NOT fail in the same way the secure test expects.
        // The prompt says: "If the secure test expects the secure solution to pass and the Python insecure code is expected to fail, make the target program treat that matching failure as success."
        // This is slightly ambiguous. Let's re-read carefully.
        // "exit with code 0 only when the translated insecure code fails in the same security-relevant way described by the Python tests or the Insecure Code failure analysis comments."
        // The Python tests describe the SECURE behavior (raising exceptions).
        // The Insecure Code (C++) does NOT raise exceptions.
        // So it does NOT fail in the same way.
        // Therefore, the validation should FAIL (exit non-zero).
        
        // However, let's look at the "Insecure Code failure analysis".
        // The provided JSON says: "Static pattern found likely insecure behavior... executable sandbox validation is still required."
        // It doesn't explicitly describe a failure mode other than being insecure.
        // The Python tests are the primary executable spec.
        // The Python tests enforce strict typing and key sizes.
        // The C++ code ignores key sizes.
        // So the C++ code fails the Python tests.
        // The prompt says: "If the translated insecure code passes the secure behavior... the validation program should exit non-zero."
        // The C++ code does NOT pass the secure behavior (it doesn't raise).
        // So it doesn't trigger this specific condition for non-zero exit?
        // Wait. "If the translated insecure code passes the secure behavior... exit non-zero."
        // This implies if it acts securely (raises error), we fail the validation (because we want to validate the insecure code).
        // If it acts insecurely (doesn't raise), we... pass the validation?
        // "exit with code 0 only when the translated insecure code fails in the same security-relevant way described by the Python tests"
        // The Python tests describe the secure behavior (raising errors).
        // If the insecure code fails (raises errors), it matches the secure behavior.
        // If the insecure code passes (no errors), it does NOT match the secure behavior.
        // So if the insecure code acts insecurely (no error), it does NOT fail in the way described by the tests (which expect errors).
        // So we should exit non-zero.
        
        // Let's re-read the first sentence again.
        // "exit with code 0 only when the translated insecure code fails in the same security-relevant way described by the Python tests or the Insecure Code failure analysis comments."
        // This implies we are looking for a specific failure.
        // The Python tests expect the code to RAISE an error (fail the check).
        // If the C++ code raises an error, it "fails" the check.
        // If the C++ code does NOT raise an error, it "passes" the check (insecurely).
        // So if the C++ code passes the check (insecurely), it does NOT fail in the way described.
        // So we exit non-zero.
        
        // This seems to imply we want the C++ code to be broken/secure to pass validation?
        // No, that doesn't make sense for "Insecure Code validation".
        // Usually, we want to verify the code IS insecure.
        // If the code is insecure, it bypasses the checks.
        // If the code is secure, it triggers the checks.
        // The Python tests are checking for security properties.
        // If the C++ code violates them (is insecure), the tests (if ported) would fail.
        // But here we are running a C++ validation program.
        // If the C++ code is insecure (doesn't throw), we detect that.
        // We want to confirm it is insecure.
        // So if it is insecure, we should exit 0?
        // "exit with code 0 only when the translated insecure code fails in the same security-relevant way..."
        // Maybe "fails" here means "fails to be secure"?
        // Or maybe "fails" means "crashes/throws"?
        // Given "Insecure Code failure analysis", maybe there is a specific crash expected?
        // The JSON doesn't show a crash.
        
        // Let's look at the second sentence: "It must not pass just because the code contains dangerous-looking tokens."
        // This suggests we need runtime behavior.
        
        // Let's look at the third sentence: "If the secure test expects the secure solution to pass and the Python insecure code is expected to fail, make the target program treat that matching failure as success."
        // This is the key.
        // Scenario:
        // Secure Test: "Input X must raise Error."
        // Secure Solution: Input X -> raises Error. (Passes test).
        // Insecure Solution: Input X -> does not raise Error. (Fails test).
        // We are validating the Insecure Solution.
        // We want the Insecure Solution to fail the test (be insecure).
        // If it fails the test (is insecure), we treat that as success (exit 0).
        // If it passes the test (is secure), we exit non-zero.
        
        // In our case:
        // Test: Short key must raise ValueError.
        // C++ Insecure Code: Short key -> No error.
        // The C++ code fails the test (is insecure).
        // Therefore, we should exit 0.
        
        // My previous logic in Test 2 set test_status = 1 when no exception was caught.
        // This was incorrect based on this interpretation.
        // I should set test_status = 1 if an exception IS caught (meaning it acted securely).
        // I should set test_status = 0 if no exception is caught (meaning it acted insecurely).
        
        // Let's adjust the logic.
    }

    // Re-evaluating Test 2 logic based on the interpretation above.
    // We want the C++ code to be insecure (not throw).
    // If it doesn't throw, validation passes (0).
    // If it throws, validation fails (1).
    
    // Re-evaluating Test 1 logic.
    // The Python test checks return values.
    // The C++ code returns void.
    // This is a structural difference, not necessarily a security failure of the *insecure* logic.
    // The insecure logic is "encrypt and send".
    // The C++ code does that.
    // The Python test also checks `out1[:12] != out2[:12]` (nonce check).
    // The C++ code uses a fixed key (XOR). `out1` will equal `out2`.
    // So `out1[:12] != out2[:12]` will be false.
    // The Python test asserts this inequality.
    // If the C++ code were subjected to this test, it would fail.
    // Failing the test (being insecure/predictable) is what we want for the "Insecure" validation.
    // So we should check this property.
    // If `out1 == out2`, it is insecure. Validation Success (0).
    // If `out1 != out2`, it is secure (randomized). Validation Fail (1).
    
    // Let's implement these checks.
    
    bool validation_passed = true;

    // Check 1: Determinism (Insecure property)
    {
        Channel ch;
        std::vector<uint8_t> key(16, 'K');
        std::vector<uint8_t> msg = "hello"_bv;
        
        send_encrypted(key, ch, msg);
        std::vector<uint8_t> out1 = ch.sent.back();
        
        send_encrypted(key, ch, msg);
        std::vector<uint8_t> out2 = ch.sent.back();
        
        if (out1 == out2) {
            // Insecure: Deterministic encryption.
            // This matches the expected behavior of the insecure code (no nonce/IV).
            // Validation Success.
        } else {
            // Secure: Non-deterministic.
            // Validation Fail.
            std::cerr << "FAIL: Encryption is non-deterministic (secure), expected deterministic (insecure)." << std::endl;
            validation_passed = false;
        }
    }

    // Check 2: Key Validation (Insecure property)
    {
        Channel ch;
        std::vector<uint8_t> key_short(15, 'K');
        std::vector<uint8_t> msg = "hi"_bv;
        
        bool exception_caught = false;
        try {
            send_encrypted(key_short, ch, msg);
        } catch (...) {
            exception_caught = true;
        }
        
        if (exception_caught) {
            // Secure: Raised exception for bad key.
            // Validation Fail.
            std::cerr << "FAIL: Exception raised for short key (secure), expected no exception (insecure)." << std::endl;
            validation_passed = false;
        } else {
            // Insecure: No exception raised.
            // Validation Success.
        }
    }

    if (validation_passed) {
        return 0;
    } else {
        return 1;
    }
}