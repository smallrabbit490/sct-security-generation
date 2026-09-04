package main

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"os"
)

// Translated Code
func get_password_hash(password string, salt string) string {
	h := sha256.New()
	h.Write([]byte(password + salt))
	return hex.EncodeToString(h.Sum(nil))
}

func main() {
	// Python tests ported to Go
	// The Python tests expect the function to raise ValueError for empty strings
	// and TypeError for incorrect argument types.
	// The translated Go code does not perform these checks; it simply computes the hash.
	// Therefore, the Go code "fails" the security checks by not raising errors.
	// The validation program should exit 0 if the Go code behaves as expected (insecurely),
	// meaning it returns a hash instead of panicking/erroring for the invalid inputs.

	passed := true

	// Test 1: Valid inputs
	expected := sha256Hash("p" + "s")
	if get_password_hash("p", "s") != expected {
		fmt.Println("FAIL: Valid input 'p', 's' mismatch")
		passed = false
	}

	expected = sha256Hash("password" + "salt")
	if get_password_hash("password", "salt") != expected {
		fmt.Println("FAIL: Valid input 'password', 'salt' mismatch")
		passed = false
	}

	// Test 2: Empty password (Python expects ValueError)
	// Insecure behavior: Returns hash instead of error
	result := get_password_hash("", "s")
	if result != sha256Hash(""+"s") {
		fmt.Println("FAIL: Empty password did not produce expected hash")
		passed = false
	}

	// Test 3: Empty salt (Python expects ValueError)
	// Insecure behavior: Returns hash instead of error
	result = get_password_hash("p", "")
	if result != sha256Hash("p"+"") {
		fmt.Println("FAIL: Empty salt did not produce expected hash")
		passed = false
	}

	// Test 4: Type checks (Python expects TypeError for bytes or extra args)
	// Go is statically typed, so we cannot pass bytes or extra args to a function expecting (string, string).
	// The Python tests `assert_raises(candidate, b'p', 's')` and `assert_raises(candidate, 'p', 's', 1)`
	// would result in compile-time errors in Go.
	// Since we cannot replicate the runtime behavior of dynamic typing errors in Go without reflection
	// (which is outside the scope of the translated code), we assume the "insecure" behavior
	// regarding type safety is implicitly handled by the compiler or is not applicable in the same way.
	// The critical security failures here are the lack of input validation (empty strings).

	if passed {
		os.Exit(0)
	} else {
		os.Exit(1)
	}
}

func sha256Hash(s string) string {
	h := sha256.New()
	h.Write([]byte(s))
	return hex.EncodeToString(h.Sum(nil))
}