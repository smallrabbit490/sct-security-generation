package main

import (
	"fmt"
	"os"
	"path/filepath"
)
// txtxml_upload_file is the translated insecure Go function.
// Insecure behavior: It does not validate file extensions, content types, or sanitize
// path traversal sequences in file_name. It blindly creates and writes to the
// concatenated directory + "/" + file_name path.
func txtxml_upload_file(file_content string, file_name string, directory string) (string, error) {
	filePath := directory + "/" + file_name

	file, err := os.Create(filePath)
	if err != nil {
		return "", err
	}
	defer file.Close()

	_, err = file.WriteString(file_content)
	if err != nil {
		return "", err
	}

	return fmt.Sprintf("File %s uploaded successfully to %s", file_name, directory), nil
}

func main() {
	directory := "./Test/CWE-434_04"

	// Clean up the test directory before starting
	os.RemoveAll(directory)
	err := os.MkdirAll(directory, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(1)
	}

	/*
		Inferred Python insecure outcome:
		The original Python code is completely insecure (CWE-434 / Path Traversal).
		It lacks any validation for file extensions, content types, or path traversal.
		The secure Python tests expect the candidate to raise exceptions for:
		- Disallowed extensions (e.g., .js)
		- Missing extensions
		- Empty file_name
		- Empty directory
		- Wrong content type (None)
		- Path traversal in file_name (../)
		However, the INSECURE Python code would simply write the file and return the
		success string for ALL of these cases (except maybe None which would raise
		a TypeError natively, but for path traversal and disallowed extensions, it
		would succeed).

		Target-language outcome being compared:
		We check that the Go translation matches the insecure behavior:
		1. It must successfully write a disallowed extension (.js) without error.
		2. It must successfully write a path traversal file_name (../ok.txt) without
		   sanitizing it to a basename, effectively writing outside the intended directory.
		If the Go code is "fixed" to be secure (e.g., validating extensions or
		sanitizing paths), these operations would fail or be rejected, and the
		validation program must exit non-zero.
	*/

	// Check 1: Insecure code must allow disallowed extensions (e.g., .js)
	// Secure code would reject this. Insecure code writes it successfully.
	jsFilePath := filepath.Join(directory, "malicious_script.js")
	result, err := txtxml_upload_file("Malicious Code", "malicious_script.js", directory)
	if err != nil {
		fmt.Fprintf(os.Stderr, "FAIL: Insecure code should allow .js extension, but got error: %v\n", err)
		os.Exit(1)
	}
	expectedResult := "File malicious_script.js uploaded successfully to " + directory
	if result != expectedResult {
		fmt.Fprintf(os.Stderr, "FAIL: Insecure code returned unexpected result for .js: got %q, want %q\n", result, expectedResult)
		os.Exit(1)
	}
	// Verify the file was actually created
	if _, err := os.Stat(jsFilePath); os.IsNotExist(err) {
		fmt.Fprintf(os.Stderr, "FAIL: Insecure code did not create the .js file\n")
		os.Exit(1)
	}

	// Check 2: Insecure code must allow path traversal in file_name without reducing to basename
	// Secure code would sanitize "../ok.txt" to "ok.txt" and write inside the directory.
	// Insecure code concatenates it directly, writing outside the directory.
	traversalFileName := "../ok.txt"
	traversalResult, err := txtxml_upload_file("OK", traversalFileName, directory)
	if err != nil {
		fmt.Fprintf(os.Stderr, "FAIL: Insecure code should allow path traversal, but got error: %v\n", err)
		os.Exit(1)
	}
	// The insecure code returns the unsanitized file_name in the success message
	expectedTraversalResult := "File ../ok.txt uploaded successfully to " + directory
	if traversalResult != expectedTraversalResult {
		fmt.Fprintf(os.Stderr, "FAIL: Insecure code returned unexpected result for traversal: got %q, want %q\n", traversalResult, expectedTraversalResult)
		os.Exit(1)
	}

	// Verify the file was created OUTSIDE the directory due to traversal
	outsideFilePath := filepath.Join(directory, traversalFileName)
	outsideFilePath = filepath.Clean(outsideFilePath)
	if _, err := os.Stat(outsideFilePath); os.IsNotExist(err) {
		fmt.Fprintf(os.Stderr, "FAIL: Insecure code did not create the path-traversed file outside the directory\n")
		os.Exit(1)
	}

	// Verify that a secure implementation (which reduces to basename) would fail this check
	// by ensuring the file was NOT created inside the directory as "ok.txt"
	insideFilePath := filepath.Join(directory, "ok.txt")
	if _, err := os.Stat(insideFilePath); !os.IsNotExist(err) {
		fmt.Fprintf(os.Stderr, "FAIL: File was created inside the directory (basename sanitized), expected it outside due to traversal\n")
		os.Exit(1)
	}

	fmt.Println("Validation passed: Insecure behavior matched.")
	os.Exit(0)
}