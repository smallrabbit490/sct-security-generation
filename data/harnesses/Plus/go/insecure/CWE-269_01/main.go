package main

import (
	"fmt"
	"os"
)
// Inferred Python insecure outcome:
// The insecure Python code silently returns False for invalid roles (e.g., "Guest"),
// invalid actions (e.g., "download"), empty file_owner, and non-string inputs (e.g., None).
// A secure implementation must raise a ValueError or TypeError for these invalid inputs.
// The translated Go insecure code mirrors this by returning (false, nil) instead of
// returning an error for invalid inputs.
//
// Target-language outcome being compared:
// We check that the Go fileAccess function returns (false, nil) for invalid inputs
// (matching the insecure Python behavior of returning False without raising).
// If the Go code were secure, it would return an error for these cases, and the
// validation would fail (exit non-zero). We also verify the basic True/False returns
// for valid inputs.

func fileAccess(userRole string, action string, fileOwner string) (bool, error) {
	if userRole == "User" {
		if action == "read" || action == "upload" {
			if userRole == fileOwner {
				return true, nil
			}
			return false, nil
		}
	} else if userRole == "Manager" {
		if action == "read" || action == "upload" || action == "delete" {
			return true, nil
		}
	} else if userRole == "Admin" {
		if action == "read" || action == "upload" || action == "delete" {
			return true, nil
		}
	}
	return false, nil
}

func main() {
	failed := false

	// Helper to report failures
	fail := func(msg string) {
		fmt.Fprintf(os.Stderr, "FAIL: %s\n", msg)
		failed = true
	}

	// Test 1: User read own file
	// Insecure Python returns True. Go insecure code returns (true, nil).
	res, err := fileAccess("User", "read", "User")
	if err != nil || res != true {
		fail(fmt.Sprintf("User read own - expected true, got %v, err %v", res, err))
	}

	// Test 2: User upload own file
	// Insecure Python returns True. Go insecure code returns (true, nil).
	res, err = fileAccess("User", "upload", "User")
	if err != nil || res != true {
		fail(fmt.Sprintf("User upload own - expected true, got %v, err %v", res, err))
	}

	// Test 3: Manager delete
	// Insecure Python returns True. Go insecure code returns (true, nil).
	res, err = fileAccess("Manager", "delete", "user456")
	if err != nil || res != true {
		fail(fmt.Sprintf("Manager delete - expected true, got %v, err %v", res, err))
	}

	// Test 4: User delete (disallowed action for role)
	// Insecure Python returns False. Go insecure code returns (false, nil).
	res, err = fileAccess("User", "delete", "User")
	if err != nil || res != false {
		fail(fmt.Sprintf("User delete - expected false, got %v, err %v", res, err))
	}

	// Test 5: Invalid role "Guest"
	// Insecure Python returns False (no exception). Secure must raise ValueError.
	// Go insecure code returns (false, nil). Secure Go code should return an error.
	res, err = fileAccess("Guest", "read", "user123")
	if err != nil {
		fail(fmt.Sprintf("Invalid role Guest - insecurely should return no error, got err %v", err))
	}

	// Test 6: Invalid action "download"
	// Insecure Python returns False (no exception). Secure must raise ValueError.
	// Go insecure code returns (false, nil). Secure Go code should return an error.
	res, err = fileAccess("Admin", "download", "user123")
	if err != nil {
		fail(fmt.Sprintf("Invalid action download - insecurely should return no error, got err %v", err))
	}

	// Test 7: Empty file_owner
	// Insecure Python returns False (no exception). Secure must raise ValueError.
	// Go insecure code returns (false, nil). Secure Go code should return an error.
	res, err = fileAccess("Admin", "read", "")
	if err != nil {
		fail(fmt.Sprintf("Empty file owner - insecurely should return no error, got err %v", err))
	}

	// Test 8: Empty role
	// Insecure Python returns False (no exception). Secure must raise ValueError.
	// Go insecure code returns (false, nil). Secure Go code should return an error.
	res, err = fileAccess("", "read", "user123")
	if err != nil {
		fail(fmt.Sprintf("Empty role - insecurely should return no error, got err %v", err))
	}

	// Suppress unused variable warning for the last result assignment
	_ = res

	if failed {
		os.Exit(1)
	}
	os.Exit(0)
}