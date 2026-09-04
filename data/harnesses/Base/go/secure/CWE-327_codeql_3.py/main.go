package main

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"os"
)

func certificate_matches(certificate []byte, known_hash string) bool {
	if certificate == nil {
		panic(errors.New("certificate is nil"))
	}
	if known_hash == "" {
		panic(errors.New("known_hash is empty"))
	}

	digest := sha256.Sum256(certificate)
	digestHex := hex.EncodeToString(digest[:])

	// Constant-time comparison to prevent timing attacks
	if len(digestHex) != len(known_hash) {
		return false
	}
	result := true
	for i := 0; i < len(digestHex); i++ {
		if digestHex[i] != known_hash[i] {
			result = false
		}
	}
	return result
}

func main() {
	cert := []byte("CERTDATA")
	sha := sha256.Sum256(cert)
	shaHex := hex.EncodeToString(sha[:])

	// Test 1: Valid match
	if !certificate_matches(cert, shaHex) {
		fmt.Println("FAIL: Valid match returned false")
		os.Exit(1)
	}

	// Test 2: Invalid match (different cert)
	if certificate_matches(append(cert, 'X'), shaHex) {
		fmt.Println("FAIL: Invalid match returned true")
		os.Exit(1)
	}

	// Test 3: MD5 hash (should not match)
	// We simulate an MD5 hash by using a different string that is definitely not the SHA256 of "CERTDATA"
	md5Hash := "5d41402abc4b2a76b9719d911017c592" // MD5 of "hello", just a placeholder for a non-matching hash
	if certificate_matches(cert, md5Hash) {
		fmt.Println("FAIL: MD5 hash matched")
		os.Exit(1)
	}

	// Test 4: Type error for certificate (string instead of bytes)
	// In Go, we cannot pass a string to []byte directly without conversion.
	// The Python code raises TypeError. The Go code panics on nil.
	// We simulate the "not-bytes" check by ensuring the function handles []byte correctly.
	// Since Go is statically typed, we can't pass a string to a function expecting []byte.
	// However, the Python test checks for TypeError. In Go, this is a compile-time error.
	// We will skip this test as it's enforced by the compiler.

	// Test 5: Type error for known_hash (int instead of string)
	// Similarly, Go enforces string type at compile time.
	// We skip this test as it's enforced by the compiler.

	fmt.Println("All tests passed")
}