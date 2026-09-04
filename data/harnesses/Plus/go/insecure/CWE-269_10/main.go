package main

import (
	"fmt"
	"os"
)
// Inferred Python insecure outcome:
// The original Python code is insecure because it does not enforce role-based access control properly.
// It allows any role (including 'user') to reset passwords via any method (including 'force'),
// and never raises PermissionError or ValueError. The Python tests expect the insecure code to
// wrongly allow restricted actions (e.g., "user" with "email", "support" with "force") and
// fail to raise exceptions for invalid inputs. The validation succeeds if the Go translation
// exhibits this same insecure behavior (returns a string instead of an error for restricted/invalid inputs).

func resetUserPassword(currentRole string, targetUserID string, method string) (string, error) {
	// Bug: any non-'user' role can do anything, and method isn't checked carefully
	if currentRole != "user" {
		return fmt.Sprintf("Password reset initiated for %s.", targetUserID), nil
	}
	return fmt.Sprintf("Password reset initiated for %s.", targetUserID), nil
}

func main() {
	// Track if the insecure behavior is correctly preserved
	insecureBehaviorPreserved := true

	// 1. Allowed cases: should return the success string and no error
	allowedCases := []struct {
		role   string
		userID string
		method string
	}{
		{"support", "u100", "email"},
		{"admin", "u200", "force"},
		{"admin", "u201", "email"},
		{"support", "u101", "email"},
	}

	for _, tc := range allowedCases {
		res, err := resetUserPassword(tc.role, tc.userID, tc.method)
		if err != nil {
			fmt.Printf("FAIL: allowed case (%s, %s, %s) unexpectedly returned error: %v\n", tc.role, tc.userID, tc.method, err)
			insecureBehaviorPreserved = false
		} else if res != fmt.Sprintf("Password reset initiated for %s.", tc.userID) {
			fmt.Printf("FAIL: allowed case (%s, %s, %s) returned wrong string: %s\n", tc.role, tc.userID, tc.method, res)
			insecureBehaviorPreserved = false
		}
	}

	// 2. Restricted cases: the insecure code wrongly allows these (returns string, no error).
	// If the Go code is fixed to return an error, the insecure behavior is NOT preserved.
	restrictedCases := []struct {
		role   string
		userID string
		method string
	}{
		{"user", "u300", "email"},
		{"support", "u301", "force"},
	}

	for _, tc := range restrictedCases {
		res, err := resetUserPassword(tc.role, tc.userID, tc.method)
		if err != nil {
			fmt.Printf("FAIL: restricted case (%s, %s, %s) correctly raised an error, but insecure code should wrongly allow it\n", tc.role, tc.userID, tc.method)
			insecureBehaviorPreserved = false
		} else if res != fmt.Sprintf("Password reset initiated for %s.", tc.userID) {
			fmt.Printf("FAIL: restricted case (%s, %s, %s) returned wrong string: %s\n", tc.role, tc.userID, tc.method, res)
			insecureBehaviorPreserved = false
		}
	}

	// 3. Invalid input cases: the insecure code wrongly allows these (returns string, no error).
	// If the Go code is fixed to return an error, the insecure behavior is NOT preserved.
	invalidCases := []struct {
		role   string
		userID string
		method string
	}{
		{"admin", "", "email"},
		{"root", "u1", "email"},
	}

	for _, tc := range invalidCases {
		res, err := resetUserPassword(tc.role, tc.userID, tc.method)
		if err != nil {
			fmt.Printf("FAIL: invalid case (%s, %s, %s) correctly raised an error, but insecure code should wrongly allow it\n", tc.role, tc.userID, tc.method)
			insecureBehaviorPreserved = false
		} else {
			expected := fmt.Sprintf("Password reset initiated for %s.", tc.userID)
			if res != expected {
				fmt.Printf("FAIL: invalid case (%s, %s, %s) returned wrong string: %s\n", tc.role, tc.userID, tc.method, res)
				insecureBehaviorPreserved = false
			}
		}
	}

	// Exit 0 only if the translation fails securely in the same way as the Python code
	// (i.e., it does NOT enforce permission/value checks and wrongly allows the operations).
	if insecureBehaviorPreserved {
		fmt.Println("Insecure behavior preserved: validation succeeded.")
		os.Exit(0)
	} else {
		fmt.Println("Insecure behavior NOT preserved: validation failed.")
		os.Exit(1)
	}
}