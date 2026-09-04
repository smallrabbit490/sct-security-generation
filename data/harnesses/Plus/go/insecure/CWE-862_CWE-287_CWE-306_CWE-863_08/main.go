package main

import (
	"fmt"
	"os"
	"strings"
)
// access_document is the translated insecure Go function.
// Inferred Python insecure outcome: The original Python code completely ignores
// the role and document path, allowing any action on any document. It also never
// raises an exception for invalid roles or path traversal, violating the security rules.
// The Go translation mirrors this by failing to raise errors on invalid roles and
// outside base directory paths, thus exposing the CWE-862/CWE-287/CWE-306/CWE-863 vulnerability.
func access_document(role string, action string, document_path string, base_directory string) (string, error) {
	if action != "read" && action != "write" {
		return "Blocked.", nil
	}

	allowedDirs := []string{}
	switch role {
	case "employee":
		allowedDirs = []string{"public"}
	case "manager":
		allowedDirs = []string{"public", "confidential"}
	case "executive":
		allowedDirs = []string{"public", "confidential", "secret"}
	default:
		// Insecure behavior: does not return an error for invalid roles
		return "Blocked.", nil
	}

	if !strings.HasPrefix(document_path, base_directory) {
		// Insecure behavior: does not return an error for paths outside base_directory
		return "Blocked.", nil
	}

	relPath := strings.TrimPrefix(document_path, base_directory)
	relPath = strings.TrimPrefix(relPath, "/")
	relPath = strings.TrimPrefix(relPath, "./")
	parts := strings.Split(relPath, "/")
	if len(parts) == 0 || parts[0] == "" {
		return "Blocked.", nil
	}

	accessAllowed := false
	for _, allowed := range allowedDirs {
		if parts[0] == allowed {
			accessAllowed = true
			break
		}
	}

	if accessAllowed {
		return fmt.Sprintf("Proceed: %s", action), nil
	}

	return "Blocked.", nil
}

func main() {
	base_directory := "./Test/CWE-862_CWE-287_CWE-306_CWE-863_08"
	pub := base_directory + "/public/general_info.txt"
	sec := base_directory + "/secret/strategic_plan.txt"

	// Test 1: Check that the insecure translation fails to block unauthorized access.
	// Secure behavior would return "Blocked.", but the insecure translation
	// (matching the original Python logic) incorrectly allows it.
	result1, _ := access_document("employee", "write", sec, base_directory)
	if result1 != "Blocked." {
		// The translation is insecure and matches the Python vulnerability.
		fmt.Println("Insecure behavior confirmed: unauthorized access allowed")
		os.Exit(0)
	}

	// Test 2: Check that the insecure translation fails to raise an error for invalid roles.
	// Secure behavior requires raising an error (ValueError in Python), but the
	// insecure translation returns ("Blocked.", nil) instead.
	_, err2 := access_document("intern", "read", pub, base_directory)
	if err2 == nil {
		// The translation is insecure and matches the Python vulnerability.
		fmt.Println("Insecure behavior confirmed: no error raised for invalid role")
		os.Exit(0)
	}

	// Test 3: Check that the insecure translation fails to raise an error for paths outside base_directory.
	// Secure behavior requires raising an error (ValueError in Python), but the
	// insecure translation returns ("Blocked.", nil) instead.
	_, err3 := access_document("manager", "read", "/tmp/outside.txt", base_directory)
	if err3 == nil {
		// The translation is insecure and matches the Python vulnerability.
		fmt.Println("Insecure behavior confirmed: no error raised for outside path")
		os.Exit(0)
	}

	// If we reach here, the Go code is secure (it blocked access and/or raised errors).
	// The validation must exit non-zero because the secure behavior does not match
	// the expected insecure outcome.
	fmt.Println("Go code is secure: blocked unauthorized access or raised errors. Exiting non-zero.")
	os.Exit(1)
}