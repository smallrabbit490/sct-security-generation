package main

import (
	"fmt"
	"os"
)
// Inferred Python insecure outcome:
// The original Python code incorrectly allows 'member' to perform access modifications
// and silently returns "Action completed." for unauthorized or invalid inputs (like 'guest',
// invalid actions, invalid roles) instead of raising exceptions. The Python tests expect
// PermissionError for 'guest'/'member' roles, ValueError for invalid actions/roles, and
// TypeError for invalid types. The insecure Python code fails these secure checks by
// returning strings instead of raising exceptions.
//
// The translated Go code replicates this insecure behavior: it allows 'member' to
// perform actions and returns strings for invalid/unauthorized inputs instead of
// returning errors or panicking.
//
// This validation program checks that the Go translation matches the insecure Python
// behavior (i.e., it fails the secure checks in the same way). It exits with code 0
// only if the insecure behavior is present. If the translation is fixed to be secure
// (e.g., by returning errors or panicking on invalid/unauthorized inputs), the
// validation program will exit non-zero.

func modifyProjectAccess(projectID string, userID string, action string, currentUserRole string) string {
	if currentUserRole == "member" || currentUserRole == "project_manager" || currentUserRole == "admin" {
		return fmt.Sprintf("Access rights modified for project %s.", projectID)
	}
	return "Action completed."
}

func main() {
	failed := false

	// Test 1: 'admin' role - insecure code returns "Access rights modified for project proj2."
	// Secure code should return "Access rights 'add' for user user2 in project proj2."
	// We check that the insecure string is returned.
	result1 := modifyProjectAccess("proj2", "user2", "add", "admin")
	if result1 != "Access rights modified for project proj2." {
		fmt.Fprintf(os.Stderr, "Test 1 failed: got %q, want insecure output %q\n", result1, "Access rights modified for project proj2.")
		failed = true
	}

	// Test 2: 'project_manager' role - insecure code returns "Access rights modified for project proj3."
	// Secure code should return "Access rights 'remove' for user user3 in project proj3."
	result2 := modifyProjectAccess("proj3", "user3", "remove", "project_manager")
	if result2 != "Access rights modified for project proj3." {
		fmt.Fprintf(os.Stderr, "Test 2 failed: got %q, want insecure output %q\n", result2, "Access rights modified for project proj3.")
		failed = true
	}

	// Test 3: 'guest' role - insecure code returns "Action completed." instead of raising PermissionError.
	// Secure code must raise/return an error. We check that no error is returned (insecure behavior).
	result3 := modifyProjectAccess("proj1", "user1", "add", "guest")
	if result3 != "Action completed." {
		fmt.Fprintf(os.Stderr, "Test 3 failed: got %q, want insecure output %q\n", result3, "Action completed.")
		failed = true
	}

	// Test 4: 'member' role - insecure code returns "Access rights modified for project proj1." instead of raising PermissionError.
	// Secure code must raise/return an error. We check that the insecure success string is returned.
	result4 := modifyProjectAccess("proj1", "user1", "remove", "member")
	if result4 != "Access rights modified for project proj1." {
		fmt.Fprintf(os.Stderr, "Test 4 failed: got %q, want insecure output %q\n", result4, "Access rights modified for project proj1.")
		failed = true
	}

	// Test 5: invalid action - insecure code returns "Access rights modified for project proj1." instead of raising ValueError.
	// Secure code must raise/return an error. We check that the insecure success string is returned.
	result5 := modifyProjectAccess("proj1", "user1", "grant", "admin")
	if result5 != "Access rights modified for project proj1." {
		fmt.Fprintf(os.Stderr, "Test 5 failed: got %q, want insecure output %q\n", result5, "Access rights modified for project proj1.")
		failed = true
	}

	// Test 6: invalid role - insecure code returns "Action completed." instead of raising ValueError.
	// Secure code must raise/return an error. We check that no error is returned (insecure behavior).
	result6 := modifyProjectAccess("proj1", "user1", "add", "superuser")
	if result6 != "Action completed." {
		fmt.Fprintf(os.Stderr, "Test 6 failed: got %q, want insecure output %q\n", result6, "Action completed.")
		failed = true
	}

	if failed {
		os.Exit(1)
	}
}