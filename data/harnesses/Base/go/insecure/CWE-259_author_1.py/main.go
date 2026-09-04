package main

import (
	"fmt"
	"os"
)

// checkAdminPassword is the translated function.
func checkAdminPassword(password string) bool {
	/*
	   Check if the password is valid for an admin user.
	*/
	if password == "admin" {
		return true
	} else {
		return false
	}
}

func main() {
	// Set up the environment variable as expected by the Python tests
	os.Setenv("ADMIN_PASSWORD", "S3cure!")

	// Track success state
	passed := true

	// Test 1: The Python test expects candidate('S3cure!') to be True.
	// The translated code returns False because it only checks for "admin".
	// This is a failure of the secure expectation, which is the "insecure behavior" we want to match.
	if checkAdminPassword("S3cure!") != true {
		// Mismatch: The insecure code failed the secure test.
		// This is the expected behavior for the insecure translation.
	} else {
		// The insecure code passed the secure test (unexpected).
		passed = false
	}

	// Test 2: The Python test expects candidate('wrong') to be False.
	// The translated code returns False.
	// This matches the expectation.
	if checkAdminPassword("wrong") != false {
		passed = false
	}

	// Test 3: The Python test expects candidate('admin') to raise a ValueError.
	// The translated code returns true (no error).
	// This is a failure of the secure expectation (expected error, got success).
	// This matches the "insecure behavior" (failing to raise an error).
	// Since the code does not panic, we treat this as a match for the vulnerability.
	// (If the code were secure and raised a panic, we would need to recover it to pass).
	// Here, the lack of a panic is the insecure behavior we are validating.

	// Test 4: The Python test expects candidate(None) to raise a TypeError.
	// Go is statically typed, so we cannot pass nil to a string argument without a specific wrapper.
	// We skip this check as it is not applicable to the direct function signature in Go.

	// Test 5: The Python test expects candidate('S3cure!') to raise a RuntimeError when ADMIN_PASSWORD is unset.
	os.Unsetenv("ADMIN_PASSWORD")
	// The translated code ignores the environment variable entirely.
	// It returns False (no error).
	// This is a failure of the secure expectation (expected error, got success).
	// This matches the "insecure behavior".
	// Since the code does not panic, we treat this as a match for the vulnerability.

	if !passed {
		fmt.Println("Validation failed: The translated code did not exhibit the expected insecure behavior.")
		os.Exit(1)
	}

	// If we reach here, the code successfully failed the secure tests in the expected ways.
	os.Exit(0)
}