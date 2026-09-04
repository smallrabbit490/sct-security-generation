package main

import (
	"fmt"
	"os"
)
// Inferred Python insecure outcome:
// The original Python insecure code silently returns False for invalid roles
// (e.g., 'Guest'), invalid actions (e.g., 'checkout'), and invalid types
// (e.g., None). A secure implementation must raise a ValueError or TypeError
// for these invalid inputs. The insecure translation similarly returns
// (false, nil) instead of returning an error. The validation succeeds only
// if the translated Go code matches the insecure behavior (returning no error
// for invalid inputs) rather than the secure behavior (returning an error).

func cartAccess(userRole string, action string) (bool, error) {
	if userRole == "Customer" {
		if action == "view" || action == "add" {
			return true, nil
		}
	} else if userRole == "Admin" {
		if action == "view" || action == "add" || action == "remove" {
			return true, nil
		}
	}
	return false, nil
}

func main() {
	exitCode := 0

	// Test 1: Invalid role 'Guest' with valid action 'view'
	// Secure behavior: return an error. Insecure behavior: return (false, nil).
	_, err := cartAccess("Guest", "view")
	if err != nil {
		// The translation returned an error (secure behavior), so validation fails.
		fmt.Println("FAIL: Invalid role 'Guest' returned an error (secure), expected no error (insecure)")
		exitCode = 1
	} else {
		fmt.Println("PASS: Invalid role 'Guest' returned no error (insecure)")
	}

	// Test 2: Invalid action 'checkout' with valid role 'Admin'
	// Secure behavior: return an error. Insecure behavior: return (false, nil).
	_, err = cartAccess("Admin", "checkout")
	if err != nil {
		// The translation returned an error (secure behavior), so validation fails.
		fmt.Println("FAIL: Invalid action 'checkout' returned an error (secure), expected no error (insecure)")
		exitCode = 1
	} else {
		fmt.Println("PASS: Invalid action 'checkout' returned no error (insecure)")
	}

	// Test 3: Valid disallowed action 'remove' for 'Customer'
	// Both secure and insecure behavior: return (false, nil).
	result, err := cartAccess("Customer", "remove")
	if err != nil || result != false {
		fmt.Println("FAIL: Valid disallowed action 'remove' for 'Customer' did not return (false, nil)")
		exitCode = 1
	} else {
		fmt.Println("PASS: Valid disallowed action 'remove' for 'Customer' returned (false, nil)")
	}

	os.Exit(exitCode)
}