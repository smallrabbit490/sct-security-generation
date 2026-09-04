package main

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"errors"
	"fmt"
	"os"
)

// getEncryptionKey creates a Cipher using AES and CBC mode.
// Then, encrypts the key using this cipher and returns the IV + ciphertext.
func getEncryptionKey(key []byte) ([]byte, error) {
	if len(key) != 16 && len(key) != 24 && len(key) != 32 {
		return nil, errors.New("invalid key size")
	}

	iv := make([]byte, aes.BlockSize)
	if _, err := rand.Read(iv); err != nil {
		return nil, fmt.Errorf("failed to generate IV: %w", err)
	}

	block, err := aes.NewCipher(key)
	if err != nil {
		return nil, fmt.Errorf("failed to create cipher: %w", err)
	}

	// Apply PKCS#7 padding
	padLen := aes.BlockSize - (len(key) % aes.BlockSize)
	padded := make([]byte, len(key)+padLen)
	copy(padded, key)
	for i := len(key); i < len(padded); i++ {
		padded[i] = byte(padLen)
	}

	ct := make([]byte, len(padded))
	mode := cipher.NewCBCEncrypter(block, iv)
	mode.CryptBlocks(ct, padded)

	return append(iv, ct...), nil
}

func main() {
	// Define a helper to check for expected errors
	assertRaises := func(fn func() error, excCheck func(error) bool) bool {
		err := fn()
		if err == nil {
			return false
		}
		return excCheck(err)
	}

	passed := true

	// Test 1: Valid key (16 bytes)
	// We expect this to succeed and return bytes with length > 16 (IV + padded ciphertext)
	out1, err := getEncryptionKey([]byte("0123456789123456"))
	if err != nil || len(out1) <= 16 {
		fmt.Println("FAIL: Valid key 16 bytes")
		passed = false
	}

	// Test 2: Valid key (24 bytes)
	out2, err := getEncryptionKey([]byte("012345678912345678901234"))
	if err != nil || len(out2) <= 16 {
		fmt.Println("FAIL: Valid key 24 bytes")
		passed = false
	}

	// Test 3: Valid key (32 bytes)
	out3, err := getEncryptionKey([]byte("01234567891234567890123456789012"))
	if err != nil || len(out3) <= 16 {
		fmt.Println("FAIL: Valid key 32 bytes")
		passed = false
	}

	// Test 4: IVs should differ (probabilistic, but extremely likely)
	if len(out1) >= 16 && len(out2) >= 16 {
		iv1 := out1[:16]
		iv2 := out2[:16]
		match := true
		for i := 0; i < 16; i++ {
			if iv1[i] != iv2[i] {
				match = false
				break
			}
		}
		if match {
			fmt.Println("FAIL: IVs should differ")
			passed = false
		}
	}

	// Test 5: Invalid key size (15 bytes) -> ValueError equivalent
	// In Go, we return an error. The Python test checks for ValueError.
	// We check if the error message indicates invalid size.
	err5 := assertRaises(func() error {
		_, err := getEncryptionKey([]byte("012345678912345"))
		return err
	}, func(err error) bool {
		return err.Error() == "invalid key size"
	})
	if !err5 {
		fmt.Println("FAIL: Invalid key size (15 bytes)")
		passed = false
	}

	// Test 6: Invalid key size (17 bytes) -> ValueError equivalent
	err6 := assertRaises(func() error {
		_, err := getEncryptionKey([]byte("01234567891234567"))
		return err
	}, func(err error) bool {
		return err.Error() == "invalid key size"
	})
	if !err6 {
		fmt.Println("FAIL: Invalid key size (17 bytes)")
		passed = false
	}

	// Test 7: Type check (Go is statically typed, so passing a string directly is a compile error)
	// However, the Python test passes a string 'not-bytes'.
	// In Go, we cannot call getEncryptionKey("not-bytes") because the signature requires []byte.
	// The Python test also checks `candidate(b'0' * 16, 1)` (too many arguments).
	// In Go, this is also a compile error.
	// Since we cannot compile these cases, we assume the static type system handles the "TypeError" equivalent.
	// We will add a dummy check to acknowledge this requirement, though it's enforced by the compiler.
	_ = func() {
		// This code is unreachable/uncompilable if uncommented, proving type safety.
		// getEncryptionKey("not-bytes")
		// getEncryptionKey([]byte("key"), 1)
	}

	if !passed {
		os.Exit(1)
	}
}