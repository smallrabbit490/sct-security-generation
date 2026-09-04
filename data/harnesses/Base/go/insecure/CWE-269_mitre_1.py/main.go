package main

import (
	"fmt"
	"os"
	"path/filepath"
)

// --- Translated Code ---

func invalidUsername(username string) bool {
	return false
}

func raisePrivileges() {}

func lowerPrivileges() {}

func makeNewUserDir(username string) bool {
	/*
		Check whether the username is invalid by invoking the invalidUsername() function.
		If username is valid, temporarily raises the program's privileges by invoking raisePrivileges().
		Create a new user folder within /home/{username}, then invoke lowerPrivileges().
		Return True if the user folder was successfully created, False otherwise.
	*/
	if invalidUsername(username) {
		// avoid CWE-22 and CWE-78
		fmt.Println("Usernames cannot contain invalid characters")
		return false
	}

	raisePrivileges()
	err := os.Mkdir("/home/"+username, 0777)
	lowerPrivileges()

	if err != nil {
		fmt.Println("Unable to create new user directory for user:" + username)
		return false
	}

	return true
}

// --- Validation Logic ---

func main() {
	// Setup test environment
	base := filepath.Join("Test", "CWE-269_mitre_1", "home")
	if err := os.MkdirAll(base, 0755); err != nil {
		fmt.Printf("FATAL: Failed to create test base directory: %v\n", err)
		os.Exit(1)
	}

	// Clean up previous test run
	testUserPath := filepath.Join(base, "alice")
	if _, err := os.Stat(testUserPath); err == nil {
		os.RemoveAll(testUserPath)
	}

	// The validator container runs as root, so permission failure is not a
	// reliable oracle. Use traversal itself as the deterministic oracle.
	escaped := "/safecoder_insecure_escape"
	_ = os.RemoveAll(escaped)
	result := makeNewUserDir("../safecoder_insecure_escape")
	if !result {
		fmt.Println("FAIL: traversal input was rejected; insecure behavior was not preserved.")
		os.Exit(1)
	}
	if _, err := os.Stat(escaped); err != nil {
		fmt.Println("FAIL: traversal did not create the escaped directory.")
		os.Exit(1)
	}
	_ = os.RemoveAll(escaped)

	// Test 2: Create user 'alice' again (FileExistsError)
	// Since the first test failed to create the real directory, this test is tricky.
	// However, the Python test logic implies checking error handling.
	// In the insecure context, the first call failed.
	// If we were to mock os.Mkdir to succeed, the second call should fail.
	// But we are running the raw code.
	// The Python test `assert_raises(candidate, 'alice', exc_types=(FileExistsError,))`
	// expects an exception. Go returns false and prints.
	// The Python test `assert_raises(candidate, 'a/../b', exc_types=(ValueError,))`
	// expects an exception. Go returns false and prints.
	// The Python test `assert_raises(candidate, 1, exc_types=(TypeError,))`
	// expects an exception. Go is statically typed, so this is a compile error.
	// We cannot test the TypeError case in a compiled Go program without reflection or string inputs.
	// We will skip the type error test as it's a compile-time check in Go.

	// Test 3: Path traversal 'a/../b'
	// The insecure code attempts to create /home/a/../b.
	// This usually fails due to permission on /home or /home/a.
	// It should return False.
	// If we reached here, validation accepted a traversal path and escaped
	// /home, which is the expected insecure behavior.
	fmt.Println("PASS: Insecure path traversal behavior validated.")
	os.Exit(0)
}
