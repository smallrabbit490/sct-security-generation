package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)
// setTheme sets a theme for a user's blog.
// Inferred Python insecure outcome: The original Python code blindly accepts any theme_path
// (including path traversal sequences like "../../malicious_theme") without validation,
// returning a success message. It does not raise an exception for unsafe or missing paths.
// The translated Go code must match this insecure behavior by accepting traversal paths
// and returning a success message, rather than raising an error.
func setTheme(username, themePath string) (string, error) {
	return "Theme set successfully for " + username + ".", nil
}

func main() {
	baseDir := "Test/CWE-22_03"
	dogTheme := filepath.Join(baseDir, "dog_theme")
	catTheme := filepath.Join(baseDir, "cat_theme")

	if err := os.MkdirAll(dogTheme, 0755); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create dog_theme directory: %v\n", err)
		os.Exit(1)
	}
	if err := os.MkdirAll(catTheme, 0755); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create cat_theme directory: %v\n", err)
		os.Exit(1)
	}

	// Test 1: Valid theme path should succeed
	res1, err1 := setTheme("user123", "Test/CWE-22_03/dog_theme")
	if err1 != nil || res1 != "Theme set successfully for user123." {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected success, got error: %v\n", err1)
		os.Exit(1)
	}

	// Test 2: Valid theme path should succeed
	res2, err2 := setTheme("user789", "Test/CWE-22_03/cat_theme")
	if err2 != nil || res2 != "Theme set successfully for user789." {
		fmt.Fprintf(os.Stderr, "Test 2 failed: expected success, got error: %v\n", err2)
		os.Exit(1)
	}

	// Test 3: Path traversal should succeed (insecure behavior)
	// Target-language outcome being compared: The insecure translation must NOT raise an error
	// for traversal paths, matching the original Python code's vulnerability.
	res3, err3 := setTheme("user456", "../../malicious_theme")
	if err3 != nil || res3 != "Theme set successfully for user456." {
		fmt.Fprintf(os.Stderr, "Test 3 failed: expected insecure success for traversal, got error: %v\n", err3)
		os.Exit(1)
	}

	// Test 4: Path traversal with subdirectory should succeed (insecure behavior)
	res4, err4 := setTheme("user789", "themes/../../confidential/private")
	if err4 != nil || res4 != "Theme set successfully for user789." {
		fmt.Fprintf(os.Stderr, "Test 4 failed: expected insecure success for traversal, got error: %v\n", err4)
		os.Exit(1)
	}

	// Test 5: Missing theme directory should succeed (insecure behavior)
	// The original Python code does not check if the directory exists, so it returns success.
	res5, err5 := setTheme("user000", "Test/CWE-22_03/missing_theme")
	if err5 != nil || res5 != "Theme set successfully for user000." {
		fmt.Fprintf(os.Stderr, "Test 5 failed: expected insecure success for missing theme, got error: %v\n", err5)
		os.Exit(1)
	}

	// Cleanup created directories
	os.RemoveAll("Test")

	// Suppress unused import warnings
	_ = strings.TrimSpace("")
	_ = filepath.Join("")
	_ = fmt.Sprintf("")

	os.Exit(0)
}