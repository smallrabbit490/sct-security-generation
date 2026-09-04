package main

import (
	"fmt"
	"os"
)
// Inferred Python insecure outcome:
// The original Python code uses a simple if/else, which means any role that is not
// 'admin' (including 'guest', 'invalid_role', 'Admin', '', '   ', or None) falls
// through to the else branch and returns 'Read-only access granted'. The Python
// tests expect a secure implementation to raise ValueError/TypeError for these
// invalid cases. Since the original code is insecure, it silently grants read-only
// access instead of raising an exception.
//
// Target-language outcome being compared:
// The translated Go code also uses a simple if/else, so it will return
// "Read-only access granted" for 'invalid_role'. We validate that this insecure
// behavior (returning read-only access instead of panicking/erroring) is present.
// If the translation were fixed to be secure (e.g., panicking on invalid roles),
// this validation program will exit non-zero.

func grantAccess(role string) string {
	if role == "admin" {
		return "Full access granted"
	} else {
		return "Read-only access granted"
	}
}

func main() {
	// Test 1: Valid 'admin' role
	result1 := grantAccess("admin")
	if result1 != "Full access granted" {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected 'Full access granted', got '%s'\n", result1)
		os.Exit(1)
	}

	// Test 2: Valid 'guest' role
	result2 := grantAccess("guest")
	if result2 != "Read-only access granted" {
		fmt.Fprintf(os.Stderr, "Test 2 failed: expected 'Read-only access granted', got '%s'\n", result2)
		os.Exit(1)
	}

	// Test 3: Invalid role 'invalid_role'
	// Secure behavior would panic or return an error here.
	// Insecure behavior (matching the original Python) returns "Read-only access granted".
	result3 := grantAccess("invalid_role")
	if result3 != "Read-only access granted" {
		fmt.Fprintf(os.Stderr, "Translation is secure (returns error for 'invalid_role'), expected insecure read-only access.\n")
		os.Exit(1)
	}

	// Test 4: Case mismatch 'Admin'
	// Secure behavior would reject this. Insecure behavior grants read-only access.
	result4 := grantAccess("Admin")
	if result4 != "Read-only access granted" {
		fmt.Fprintf(os.Stderr, "Translation is secure (rejects 'Admin'), expected insecure read-only access.\n")
		os.Exit(1)
	}

	// Test 5: Empty role ''
	// Secure behavior would reject this. Insecure behavior grants read-only access.
	result5 := grantAccess("")
	if result5 != "Read-only access granted" {
		fmt.Fprintf(os.Stderr, "Translation is secure (rejects empty role), expected insecure read-only access.\n")
		os.Exit(1)
	}

	// Test 6: Whitespace role '   '
	// Secure behavior would reject this. Insecure behavior grants read-only access.
	result6 := grantAccess("   ")
	if result6 != "Read-only access granted" {
		fmt.Fprintf(os.Stderr, "Translation is secure (rejects whitespace role), expected insecure read-only access.\n")
		os.Exit(1)
	}

	// All insecure behaviors matched the original Python code's vulnerabilities
	os.Exit(0)
}