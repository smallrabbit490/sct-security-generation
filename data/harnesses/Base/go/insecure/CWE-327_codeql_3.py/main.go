package main

import (
	"crypto/md5"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"os"
)

// certificate_matches is the translated insecure function.
func certificate_matches(certificate []byte, known_hash string) bool {
	hash := md5.Sum(certificate)
	return hex.EncodeToString(hash[:]) == known_hash
}

func main() {
	cert := []byte("CERTDATA")
	sha := sha256.Sum256(cert)
	shaStr := hex.EncodeToString(sha[:])
	md5Hash := md5.Sum(cert)
	md5Str := hex.EncodeToString(md5Hash[:])

	// Test 1: candidate(cert, sha) is True
	// The insecure code uses MD5, so this will be False.
	if certificate_matches(cert, shaStr) {
		fmt.Println("FAIL: Expected candidate(cert, sha) to be True, but insecure code returned False.")
		os.Exit(1)
	}

	// Test 2: candidate(cert + b'X', sha) is False
	// The insecure code uses MD5, so this will be False.
	if certificate_matches(append(cert, 'X'), shaStr) {
		fmt.Println("FAIL: Expected candidate(cert + b'X', sha) to be False, but insecure code returned True.")
		os.Exit(1)
	}

	// Test 3: Must NOT accept md5-known-hash
	// The insecure code uses MD5, so this will be True.
	// The test expects False. Since the insecure code fails this security check,
	// the validator should treat this as a success (exit 0).
	if !certificate_matches(cert, md5Str) {
		fmt.Println("FAIL: Insecure code did not return True for MD5 hash as expected.")
		os.Exit(1)
	}

	// Test 4: Type checks
	// Go is statically typed, so passing a string or int where []byte is expected
	// results in a compile-time error. We cannot test this dynamically in the same
	// way as Python without reflection or interface{} usage, which would deviate
	// from the provided translation. We assume the translation is structurally
	// correct regarding types.

	// If we reach here, the insecure code behaved exactly as expected (insecurely).
	os.Exit(0)
}