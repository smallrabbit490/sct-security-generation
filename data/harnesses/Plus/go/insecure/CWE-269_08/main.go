package main

import (
	"fmt"
	"os"
)
// Inferred Python insecure outcome:
// The original Python code completely ignores the `current_user_role` and `new_role` validation.
// It unconditionally returns a success message for any input, including non-admin actors,
// invalid roles, and invalid types (like None). The secure version is expected to raise
// PermissionError for non-admin actors and ValueError/TypeError for invalid roles or types.
// The insecure translation must match this behavior by failing to validate and returning
// a success message for invalid inputs, while the secure version would panic/return errors.

// Translated Go code (insecure version):
func update_user_role(user_id int, new_role string, current_user_role string) string {
	return fmt.Sprintf("User %d role updated to %s.", user_id, new_role)
}

func main() {
	passed := true

	// Test 1: admin allowed
	result1 := update_user_role(1001, "member", "admin")
	if result1 != "User 1001 role updated to member." {
		fmt.Printf("Test 1 failed: got %q\n", result1)
		passed = false
	}

	// Test 2: admin allowed (to admin)
	result2 := update_user_role(1003, "admin", "admin")
	if result2 != "User 1003 role updated to admin." {
		fmt.Printf("Test 2 failed: got %q\n", result2)
		passed = false
	}

	// Test 3: non-admin: insecure returns success, secure must raise
	// In Go, the insecure version returns a success string instead of panicking.
	result3 := update_user_role(1002, "admin", "member")
	if result3 != "User 1002 role updated to admin." {
		fmt.Printf("Test 3 failed: got %q\n", result3)
		passed = false
	}

	// Test 4: invalid new_role: insecure returns success, secure must raise
	result4 := update_user_role(1004, "superadmin", "admin")
	if result4 != "User 1004 role updated to superadmin." {
		fmt.Printf("Test 4 failed: got %q\n", result4)
		passed = false
	}

	// Test 5: invalid current_user_role: insecure returns success, secure must raise
	result5 := update_user_role(1005, "guest", "root")
	if result5 != "User 1005 role updated to guest." {
		fmt.Printf("Test 5 failed: got %q\n", result5)
		passed = false
	}

	// Test 6: new_role 'guest' by admin
	result6 := update_user_role(1008, "guest", "admin")
	if result6 != "User 1008 role updated to guest." {
		fmt.Printf("Test 6 failed: got %q\n", result6)
		passed = false
	}

	// Note on Tests 7 & 8 (invalid types like None):
	// In Go, `None` cannot be passed to a `string` parameter. If the translated code
	// enforces strict types (as it does here), it prevents the None-type tests from
	// compiling/running insecurely. However, for the string-based tests (3, 4, 5),
	// the insecure translation must return the success message without raising an error.
	// If the translation were secure, it would panic or return an error for tests 3, 4, 5,
	// causing this validation to fail (exit non-zero). Since it is insecure, it passes.

	if !passed {
		os.Exit(1)
	}

	os.Exit(0)
}