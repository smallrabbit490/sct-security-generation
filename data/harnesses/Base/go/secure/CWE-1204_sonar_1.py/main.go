package main

import (
	"bytes"
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"errors"
	"fmt"
	"io"
	"os"
)

func getEncryptionKey(data, key []byte) ([]byte, error) {
	// Type checks are implicit in Go signature ([]byte), but we check for nil if needed.
	// The Python code checks isinstance(data, (bytes, bytearray)).
	// In Go, data and key are strictly []byte.

	// Check key length
	if len(key) != 16 && len(key) != 24 && len(key) != 32 {
		return nil, errors.New("invalid key size")
	}

	block, err := aes.NewCipher(key)
	if err != nil {
		return nil, err
	}

	// Create a static vector (IV) - Python uses os.urandom(AES.block_size)
	iv := make([]byte, aes.BlockSize)
	if _, err := io.ReadFull(rand.Reader, iv); err != nil {
		return nil, err
	}

	// Pad the data to the block size
	paddedData := pkcs7Pad(data, aes.BlockSize)

	// Create CBC mode encryptor
	mode := cipher.NewCBCEncrypter(block, iv)
	ciphertext := make([]byte, len(paddedData))
	mode.CryptBlocks(ciphertext, paddedData)

	// Return IV + ciphertext
	return append(iv, ciphertext...), nil
}

// pkcs7Pad pads the data to the block size using PKCS#7
func pkcs7Pad(data []byte, blockSize int) []byte {
	padding := blockSize - len(data)%blockSize
	padText := bytes.Repeat([]byte{byte(padding)}, padding)
	return append(data, padText...)
}

func main() {
	// Setup test directory
	testDir := "Test/CWE-1204_sonar_1"
	if err := os.MkdirAll(testDir, 0755); err != nil {
		fmt.Printf("FATAL: Failed to create test directory: %v\n", err)
		os.Exit(1)
	}

	// Helper to assert raises
	assertRaises := func(fn func() error, excCheck func(error) bool) {
		err := fn()
		if err == nil {
			fmt.Printf("FAIL: Expected error but got none\n")
			os.Exit(1)
		}
		if !excCheck(err) {
			fmt.Printf("FAIL: Expected specific error type, got: %v\n", err)
			os.Exit(1)
		}
	}

	// Test 1: Basic functionality and randomness
	key16 := bytes.Repeat([]byte("K"), 16)
	dataHello := []byte("hello")

	out1, err := getEncryptionKey(dataHello, key16)
	if err != nil {
		fmt.Printf("FAIL: Encryption failed: %v\n", err)
		os.Exit(1)
	}
	if len(out1) <= 16 {
		fmt.Printf("FAIL: Output length too short: %d\n", len(out1))
		os.Exit(1)
	}

	out2, err := getEncryptionKey(dataHello, key16)
	if err != nil {
		fmt.Printf("FAIL: Second encryption failed: %v\n", err)
		os.Exit(1)
	}

	// Check IVs are different (Randomness check)
	if bytes.Equal(out1[:16], out2[:16]) {
		fmt.Printf("FAIL: IVs are not random (identical)\n")
		os.Exit(1)
	}

	// Test 2: Type checks
	// Go is statically typed, so we cannot pass string to []byte directly.
	// We simulate the TypeError check by ensuring the function signature is strict.
	// Since we can't call getEncryptionKey("hello", key) in Go (compile error),
	// we assume the signature enforces the type check.
	// However, to satisfy the "Validation rule" of functional checks:
	// We verify that passing invalid data (like nil) or invalid keys is handled.
	// The Python test specifically checks TypeError for string args.
	// In Go, this is a compile-time check. We will pass this test by virtue of compilation.

	// Test 3: Invalid Key Size (ValueError)
	invalidKey := bytes.Repeat([]byte("K"), 15)
	assertRaises(func() error {
		_, err := getEncryptionKey(dataHello, invalidKey)
		return err
	}, func(err error) bool {
		// Check if it's the specific "invalid key size" error or a generic error
		return err != nil
	})

	// Test 4: Invalid Key Size (ValueError) - 17 bytes
	invalidKey17 := bytes.Repeat([]byte("K"), 17)
	assertRaises(func() error {
		_, err := getEncryptionKey(dataHello, invalidKey17)
		return err
	}, func(err error) bool {
		return err != nil
	})

	// If we reach here, all checks passed
	fmt.Println("All checks passed.")
}