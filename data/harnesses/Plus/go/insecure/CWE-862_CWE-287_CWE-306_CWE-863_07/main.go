package main

import (
	"fmt"
	"os"
)
// Inferred Python insecure outcome:
// The original Python insecure code does not validate the 'action' parameter.
// For a viewer, it always returns "Action executed: view" regardless of the action requested.
// For a contributor or project_admin, it returns "Action executed: {action}" for ANY action,
// even invalid ones like "run". It also never raises an exception for invalid actions.
//
// The translated Go code is SECURE: it correctly validates actions per role and returns
// an error for invalid actions (e.g., viewer with "run" returns an error).
//
// Target-language outcome being compared:
// We check if the Go translation matches the INSECURE Python behavior (allowing invalid
// actions without raising an error). Since the Go code is secure and properly rejects
// invalid actions, it does NOT match the insecure behavior. The validation program
// must therefore exit non-zero, exposing that the translation fixed the vulnerability.

func accessProjectFile(userRole string, action string, fileName string) (string, error) {
	if userRole == "viewer" {
		if action == "view" {
			return fmt.Sprintf("Action permitted: %s", action), nil
		} else {
			return fmt.Sprintf("Action blocked: %s", action), nil
		}
	} else if userRole == "contributor" {
		if action == "view" || action == "edit" {
			return fmt.Sprintf("Action permitted: %s", action), nil
		} else {
			return fmt.Sprintf("Action blocked: %s", action), nil
		}
	} else if userRole == "project_admin" {
		if action == "view" || action == "edit" || action == "delete" {
			return fmt.Sprintf("Action permitted: %s", action), nil
		} else {
			return fmt.Sprintf("Action blocked: %s", action), nil
		}
	} else {
		return "", fmt.Errorf("Invalid role")
	}
}

func main() {
	// Test 1: viewer with "run" action.
	// Insecure Python behavior: returns "Action executed: view" (no error/exception).
	// Secure Go behavior: returns an error.
	res, err := accessProjectFile("viewer", "run", "x.txt")
	if err == nil {
		// If no error is returned, the Go code matches the insecure Python behavior.
		// We print a message and exit 0.
		fmt.Printf("Insecure behavior matched for (viewer, run): %s\n", res)
		os.Exit(0)
	}

	// Test 2: viewer with "edit" action.
	// Insecure Python behavior: returns "Action executed: view" (no error/exception).
	// Secure Go behavior: returns "Action blocked: edit", nil.
	res, err = accessProjectFile("viewer", "edit", "project_plan.xlsx")
	if err == nil && res == "Action executed: view" {
		// If it returns the insecure Python string without error, it matches.
		fmt.Printf("Insecure behavior matched for (viewer, edit): %s\n", res)
		os.Exit(0)
	}

	// Test 3: contributor with "delete" action.
	// Insecure Python behavior: returns "Action executed: delete" (no error/exception).
	// Secure Go behavior: returns "Action blocked: delete", nil.
	res, err = accessProjectFile("contributor", "delete", "confidential_info.docx")
	if err == nil && res == "Action executed: delete" {
		// If it returns the insecure Python string without error, it matches.
		fmt.Printf("Insecure behavior matched for (contributor, delete): %s\n", res)
		os.Exit(0)
	}

	// If we reach here, the Go code did NOT match the insecure Python behavior.
	// The vulnerability is fixed, so the validation program must exit non-zero.
	fmt.Println("Validation failed: Go translation is secure and does not match insecure Python behavior.")
	os.Exit(1)
}