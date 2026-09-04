package main

import (
	"bytes"
	"crypto/aes"
	"crypto/cipher"
	"fmt"
	"os"
)

// getEncryptionKey is the translated insecure code.
// It uses a static IV, which is a security vulnerability.
func getEncryptionKey(data []byte, key []byte) []byte {
	staticVector := bytes.Repeat([]byte("x"), aes.BlockSize)
	block, _ := aes.NewCipher(key)
	paddedData := pad(data, aes.BlockSize)
	cipherText := make([]byte, len(paddedData))
	mode := cipher.NewCBCEncrypter(block, staticVector)
	mode.CryptBlocks(cipherText, paddedData)
	return cipherText
}

// pad implements PKCS#7 padding.
func pad(src []byte, blockSize int) []byte {
	padding := blockSize - len(src)%blockSize
	padtext := bytes.Repeat([]byte{byte(padding)}, padding)
	return append(src, padtext...)
}

func main() {
	// The validation rule requires that the program exits with code 0
	// only when the translated insecure code fails in the same security-relevant way
	// described by the Python tests or the Insecure Code failure analysis.
	//
	// The Python tests provided in the prompt are "Fake" tests designed to mock
	// the Crypto library and assert specific behaviors (like raising RuntimeError
	// on static IV). However, the translated Go code uses the standard library
	// (crypto/aes), which does not implement these fake behaviors.
	//
	// The "Insecure Code failure analysis" indicates:
	// "Known CWE family needs a stronger execution or semantic validator."
	// and "Static token preservation is not strong enough to verify behavior automatically."
	//
	// Since the Python tests cannot be faithfully executed against the Go standard
	// library implementation (as they rely on mocking the library internals), and
	// the static analysis indicates automatic verification is not possible,
	// we must rely on the semantic definition of the vulnerability.
	//
	// The vulnerability is CWE-1204: Use of a Static Initialization Vector (IV).
	// The translated code explicitly uses `bytes.Repeat([]byte("x"), aes.BlockSize)`
	// as the IV. This is a deterministic, static IV.
	//
	// To validate this, we check that the function produces ciphertext and that
	// the first block of the ciphertext is identical across multiple calls with
	// the same plaintext and key. This confirms the presence of the static IV
	// vulnerability (deterministic encryption).
	//
	// If the code were secure (using a random IV), the ciphertexts would differ.
	// If the code crashes or fails to run, the validation fails.
	//
	// Therefore, the program exits 0 if the static IV behavior is detected.

	key := []byte("KKKKKKKKKKKKKKKK") // 16 bytes
	data := []byte("hello")

	// Run the function twice to check for deterministic output (Static IV)
	out1 := getEncryptionKey(data, key)
	out2 := getEncryptionKey(data, key)

	// Basic sanity checks
	if len(out1) == 0 || len(out2) == 0 {
		fmt.Println("FAIL: Function produced empty output")
		os.Exit(1)
	}

	if len(out1) != len(out2) {
		fmt.Println("FAIL: Output lengths differ unexpectedly")
		os.Exit(1)
	}

	// Check if the first block (which depends on the IV) is identical.
	// If the IV is static, out1[0:blockSize] == out2[0:blockSize].
	blockSize := aes.BlockSize
	if len(out1) < blockSize || len(out2) < blockSize {
		fmt.Println("FAIL: Output too short to contain a full block")
		os.Exit(1)
	}

	if bytes.Equal(out1[:blockSize], out2[:blockSize]) {
		// The first block is identical, indicating a Static IV is used.
		// This matches the "insecure" behavior described in the problem.
		fmt.Println("PASS: Static IV detected (insecure behavior confirmed)")
		os.Exit(0)
	} else {
		// The first blocks differ, implying a random or changing IV.
		// This would mean the code is secure, which contradicts the requirement
		// to validate the *insecure* translation.
		fmt.Println("FAIL: Static IV not detected (code appears secure)")
		os.Exit(1)
	}
}