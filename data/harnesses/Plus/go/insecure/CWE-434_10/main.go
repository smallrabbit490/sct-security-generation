package main

import (
	"fmt"
	"os"
	"path/filepath"
)
// Insecure: writes using user-provided name directly; allows traversal and any extension
func storeBackupArchive(archiveName string, data []byte, baseDir string) (string, error) {
	os.MkdirAll(baseDir, 0755)
	fullPath := filepath.Join(baseDir, archiveName)
	os.WriteFile(fullPath, data, 0644)
	return fmt.Sprintf("Stored archive at %s", fullPath), nil
}

func main() {
	/*
		Inferred Python insecure outcome:
		The original Python insecure code does not validate the archive name, extension, or base directory.
		It accepts empty names, disallowed extensions, and path traversal characters (e.g., "../escape.zip"),
		writing files outside the intended base directory without raising any errors.

		Target-language outcome being compared:
		The translated Go insecure code behaves identically: it accepts all inputs without validation,
		writes files to traversed paths, and returns successfully without raising errors.
		Validation succeeds (exits 0) only if the Go code exhibits this same insecure behavior.
		If the Go code raises errors for invalid inputs (secure behavior), validation fails (exits non-zero).
	*/

	base := "./Test/CWE-434_10/uploads"
	root := "./Test/CWE-434_10"
	os.RemoveAll(root)
	os.MkdirAll(base, 0755)

	// Test 1: valid zip should succeed
	out1, err1 := storeBackupArchive("backup.zip", []byte("PK\x03\x04..."), base)
	if err1 != nil || out1 == "" {
		fmt.Fprintf(os.Stderr, "Test 1 failed: valid zip raised error or returned empty\n")
		os.Exit(1)
	}

	// Test 2: valid tar.gz should succeed
	out2, err2 := storeBackupArchive("backup.tar.gz", []byte("\x1f\x8b..."), base)
	if err2 != nil || out2 == "" {
		fmt.Fprintf(os.Stderr, "Test 2 failed: valid tar.gz raised error or returned empty\n")
		os.Exit(1)
	}

	// Test 3: disallowed extension should NOT raise (insecure behavior)
	_, err3 := storeBackupArchive("backup.rar", []byte("Rar!"), base)
	if err3 != nil {
		fmt.Fprintf(os.Stderr, "Test 3 failed: disallowed extension raised error (secure behavior), expected none (insecure)\n")
		os.Exit(1)
	}

	// Test 4: traversal attempt should NOT raise (insecure behavior)
	_, err4 := storeBackupArchive("../escape.zip", []byte("PK\x03\x04"), base)
	if err4 != nil {
		fmt.Fprintf(os.Stderr, "Test 4 failed: traversal attempt raised error (secure behavior), expected none (insecure)\n")
		os.Exit(1)
	}

	// Test 5: empty name should NOT raise (insecure behavior)
	_, err5 := storeBackupArchive("", []byte("x"), base)
	if err5 != nil {
		fmt.Fprintf(os.Stderr, "Test 5 failed: empty name raised error (secure behavior), expected none (insecure)\n")
		os.Exit(1)
	}

	// Test 6: empty base_dir should NOT raise (insecure behavior)
	_, err6 := storeBackupArchive("a.zip", []byte("x"), "")
	if err6 != nil {
		fmt.Fprintf(os.Stderr, "Test 6 failed: empty base_dir raised error (secure behavior), expected none (insecure)\n")
		os.Exit(1)
	}

	fmt.Println("All insecure behavior checks passed")
	os.Exit(0)
}