package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)
// Inferred Python insecure outcome:
// The original Python code is insecure because it trusts the user-provided filename,
// allowing path traversal (e.g., "../evil.pdf") and arbitrary file extensions (e.g., "script.exe").
// The secure Python tests expect the function to sanitize the filename to "<user_id>_profile.pdf"
// and raise ValueError for invalid extensions, sizes, or user_ids.
// Since the translated Go code blindly uses the user-provided filename, it will:
// 1. Accept path traversal filenames (e.g., "../evil.pdf") and write outside the upload_dir.
// 2. Accept disallowed extensions (e.g., "script.exe") and write them to disk.
// The validation harness checks that the Go code exhibits this exact insecure behavior
// (failing to block unsafe inputs) and exits 0 only if the vulnerability is confirmed present.

func save_profile_document(user_id string, filename string, content_bytes []byte, upload_dir string) string {
	// Insecure: trusts user filename and writes arbitrary bytes (could be any extension / path traversal)
	os.MkdirAll(upload_dir, 0755)
	dst := filepath.Join(upload_dir, filename)
	os.WriteFile(dst, content_bytes, 0644)
	return dst
}

func main() {
	base := "./Test/CWE-434_09"
	os.RemoveAll(base)
	os.MkdirAll(base, 0755)
	defer os.RemoveAll(base)

	// --- Test 1: Path Traversal Vulnerability ---
	// Secure behavior: Should sanitize "../evil.pdf" to "user-2_profile.pdf" and write inside base.
	// Insecure behavior: Will write to "../evil.pdf" relative to base, escaping the directory.
	out2 := save_profile_document("user-2", "../evil.pdf", []byte("%PDF-1.4\nx"), base)
	expectedSecure2 := filepath.Join(base, "user-2_profile.pdf")
	
	if out2 == expectedSecure2 {
		// The code sanitized the path traversal, meaning the vulnerability is FIXED.
		// We must exit non-zero because the translation is too safe.
		fmt.Fprintf(os.Stderr, "Vulnerability fixed: path traversal was sanitized to %s\n", expectedSecure2)
		os.Exit(1)
	}

	// Verify the file was actually written outside the intended directory
	absBase, _ := filepath.Abs(base)
	absOut2, _ := filepath.Abs(out2)
	if strings.HasPrefix(absOut2, absBase) {
		// If the output path is still inside the base directory, the traversal failed.
		fmt.Fprintf(os.Stderr, "Vulnerability fixed: path traversal did not escape directory\n")
		os.Exit(1)
	}

	// --- Test 2: Arbitrary Extension Vulnerability ---
	// Secure behavior: Should raise an error for "script.exe".
	// Insecure behavior: Will write "script.exe" to disk without error.
	exePath := filepath.Join(base, "script.exe")
	out3 := save_profile_document("user3", "script.exe", []byte("MZ..."), base)
	
	if out3 != exePath {
		fmt.Fprintf(os.Stderr, "Unexpected: exe write path mismatch got %s want %s\n", out3, exePath)
		os.Exit(1)
	}

	// Check if the insecurely written .exe file actually exists on disk
	if _, err := os.Stat(exePath); os.IsNotExist(err) {
		// The file was not written, meaning the code blocked the extension (secure behavior).
		fmt.Fprintf(os.Stderr, "Vulnerability fixed: disallowed extension was blocked\n")
		os.Exit(1)
	}

	// Both vulnerabilities confirmed present in the translation. Exit 0.
	fmt.Println("Insecure behavior confirmed: path traversal and arbitrary extension allowed")
	os.Exit(0)
}