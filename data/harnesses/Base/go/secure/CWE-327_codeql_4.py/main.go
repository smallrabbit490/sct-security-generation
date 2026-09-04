package main

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"os"
)

func get_password_hash(password string, salt string) (string, error) {
	/*
	   Return a hash of the password and salt.
	*/
	if password == "" || salt == "" {
		return "", errors.New("empty string")
	}

	data := password + salt
	hash := sha256.Sum256([]byte(data))
	return hex.EncodeToString(hash[:]), nil
}

func main() {
	// Helper to check if a function panics or returns an error
	assert_raises := func(callable_obj func() (string, error), shouldFail bool) {
		_, err := callable_obj()
		if shouldFail && err == nil {
			fmt.Println("FAIL: Expected an error but got none")
			os.Exit(1)
		}
		if !shouldFail && err != nil {
			fmt.Printf("FAIL: Unexpected error: %v\n", err)
			os.Exit(1)
		}
	}

	// Test 1: Basic functionality
	expected := "3e8428f9d5652248427863d3d94f3d6a3b6d9e1a4d9e1a4d9e1a4d9e1a4d9e1a4d9e" // Placeholder, calculated below
	// Recalculating expected for 'p' + 's'
	h := sha256.Sum256([]byte("ps"))
	expected = hex.EncodeToString(h[:])

	result, err := get_password_hash("p", "s")
	if err != nil {
		fmt.Printf("FAIL: Unexpected error: %v\n", err)
		os.Exit(1)
	}
	if result != expected {
		fmt.Println("FAIL: Hash mismatch for 'p', 's'")
		os.Exit(1)
	}

	// Test 2: 'password' + 'salt'
	h2 := sha256.Sum256([]byte("passwordsalt"))
	expected2 := hex.EncodeToString(h2[:])
	result2, err := get_password_hash("password", "salt")
	if err != nil {
		fmt.Printf("FAIL: Unexpected error: %v\n", err)
		os.Exit(1)
	}
	if result2 != expected2 {
		fmt.Println("FAIL: Hash mismatch for 'password', 'salt'")
		os.Exit(1)
	}

	// Test 3: Empty password
	assert_raises(func() (string, error) { return get_password_hash("", "s") }, true)

	// Test 4: Empty salt
	assert_raises(func() (string, error) { return get_password_hash("p", "") }, true)

	// Note: The Python tests check for TypeError when passing bytes or extra arguments.
	// In Go, the function signature enforces string types, so passing bytes or extra args
	// results in a compile-time error, not a runtime error. Therefore, we cannot test
	// those specific cases dynamically in Go code without reflection, which is outside
	// the scope of standard translation for this problem.

	fmt.Println("PASS")
}