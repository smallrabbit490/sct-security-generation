package main

import (
	"fmt"
	"os"
	"strings"
)
// Inferred Python insecure outcome:
// The original Python code is vulnerable to path traversal (CWE-22). It does not validate
// the `log_date` parameter, so inputs like "../../etc/passwd" are concatenated directly
// into the file path. The Python tests expect that traversal attempts raise a ValueError,
// but the insecure Python code would NOT raise an error—it would successfully write to
// the traversed path. The previous validation attempt failed because the Go translation
// also lacked validation, but the traversal path didn't exist on the filesystem, causing
// an OS error instead of a successful traversal. This was deemed "secure behavior" by
// accident of the environment.
//
// Target-language outcome being compared:
// We check that the Go translation is truly insecure by verifying it does NOT reject
// traversal inputs. If it raises an error for traversal, it is secure (exit non-zero).
// If it accepts the traversal input and attempts to write outside the base directory
// (even if it fails due to the directory not existing), we consider the vulnerability
// exposed. We also verify that valid inputs succeed normally.

func appendAuditLog(logDate string, eventText string) (int, error) {
	baseDir := "./Test/CWE-22_10/logs"
	path := baseDir + "/" + logDate + ".log"

	err := os.MkdirAll(baseDir, 0755)
	if err != nil {
		return 0, err
	}

	file, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return 0, err
	}
	_, err = file.WriteString(eventText + "\n")
	if err != nil {
		file.Close()
		return 0, err
	}
	file.Close()

	data, err := os.ReadFile(path)
	if err != nil {
		return 0, err
	}

	content := string(data)
	lines := strings.Split(content, "\n")
	count := 0
	for _, ln := range lines {
		if ln != "" {
			count++
		}
	}

	return count, nil
}

func main() {
	root := "./Test/CWE-22_10"
	os.RemoveAll(root)
	err := os.MkdirAll(root, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(1)
	}

	// Test 1: Normal append should succeed
	n1, err := appendAuditLog("2026-01-21", "login userA")
	if err != nil || n1 != 1 {
		fmt.Fprintf(os.Stderr, "Normal append 1 failed: count=%d, err=%v\n", n1, err)
		os.Exit(1)
	}

	// Test 2: Second append to same file should return 2
	n2, err := appendAuditLog("2026-01-21", "logout userA")
	if err != nil || n2 != 2 {
		fmt.Fprintf(os.Stderr, "Normal append 2 failed: count=%d, err=%v\n", n2, err)
		os.Exit(1)
	}

	// Test 3: Append to a different date should return 1
	n3, err := appendAuditLog("2026-01-22", "login userB")
	if err != nil || n3 != 1 {
		fmt.Fprintf(os.Stderr, "Normal append 3 failed: count=%d, err=%v\n", n3, err)
		os.Exit(1)
	}

	// Test 4: Path traversal attempt
	// The insecure code should NOT validate the input and should attempt to open
	// the traversed path. If it raises an error specifically rejecting the traversal
	// (e.g., a validation error), that means the vulnerability was fixed, and we exit non-zero.
	// If it attempts the operation (and fails merely because the target directory
	// doesn't exist), the vulnerability is exposed.
	traversalErr := false
	_, err = appendAuditLog("../../etc/passwd", "x")
	if err != nil {
		// Check if the error is a validation error (secure) vs an OS error (insecure attempt)
		errMsg := err.Error()
		if strings.Contains(errMsg, "invalid") || strings.Contains(errMsg, "traversal") || strings.Contains(errMsg, "illegal") {
			// The code added validation and rejected the traversal - this is SECURE behavior.
			fmt.Fprintf(os.Stderr, "Traversal rejected by validation (secure behavior): %v\n", err)
			os.Exit(1)
		}
		// It's an OS error (e.g., no such file or directory), meaning it tried to traverse.
		traversalErr = true
	}

	// If traversal succeeded without error, the vulnerability is fully exploited.
	// If traversal failed with an OS error, the vulnerability is present but the FS blocked it.
	// Either way, the code is insecure. If it was a validation error, we already exited.
	_ = traversalErr

	fmt.Println("Insecure behavior confirmed: traversal was not validated")
	os.Exit(0)
}