package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)
// serveResource is the translated insecure Go function.
// Insecure Python outcome: The function concatenates user input directly into a file path
// without sanitization, allowing path traversal. It returns "Resource not found." for
// non-existent files instead of raising an exception, and it does not raise exceptions
// for traversal attempts like "../etc/passwd".
func serveResource(filePath string) string {
	baseDir := "./Test/CWE-22_07/resources"
	fullPath := baseDir + "/" + filePath

	data, err := os.ReadFile(fullPath)
	if err != nil {
		if os.IsNotExist(err) {
			return "Resource not found."
		}
		return fmt.Sprintf("Error reading file: %v", err)
	}

	return string(data)
}

func main() {
	baseDir := "./Test/CWE-22_07/resources"
	outsideDir := "./Test/CWE-22_07"

	// Setup directory structure
	os.MkdirAll(baseDir, 0755)

	// Create a normal test file inside the resources directory
	testFilePath := filepath.Join(baseDir, "test_file.txt")
	os.WriteFile(testFilePath, []byte("This is a test file."), 0644)

	// Create a file outside the resources directory to test path traversal
	outsideFilePath := filepath.Join(outsideDir, "outside_file.txt")
	os.WriteFile(outsideFilePath, []byte("Outside content."), 0644)

	passed := true

	// Test 1: Normal file read should succeed
	result := serveResource("test_file.txt")
	if result != "This is a test file." {
		fmt.Printf("FAIL: Normal file read failed. Got: %q\n", result)
		passed = false
	}

	// Test 2: Path traversal must succeed (insecure behavior).
	// The insecure Python code simply concatenates the path, so "../outside_file.txt"
	// resolves to a file outside the base directory and returns its content.
	// If the translation is secure, it will block traversal and return "Resource not found."
	// or an error, which would be a failure for this insecure validation.
	traversalResult := serveResource("../outside_file.txt")
	if traversalResult != "Outside content." {
		fmt.Printf("FAIL: Path traversal '../outside_file.txt' did not return 'Outside content.'. Got: %q\n", traversalResult)
		passed = false
	}

	// Test 3: Non-existent file must return "Resource not found." instead of raising an error.
	// The insecure Python code catches FileNotFoundError and returns "Resource not found."
	missingResult := serveResource("nonexistent.txt")
	if missingResult != "Resource not found." {
		fmt.Printf("FAIL: Missing file did not return 'Resource not found.'. Got: %q\n", missingResult)
		passed = false
	}

	// Test 4: Type error simulation. Go is statically typed, so passing nil/None is
	// a compile-time error. We simulate the equivalent insecure behavior by ensuring
	// an empty string doesn't crash unexpectedly and follows the same path logic.
	emptyResult := serveResource("")
	if !strings.Contains(emptyResult, "not found") && !strings.Contains(emptyResult, "Error") {
		fmt.Printf("FAIL: Empty string path did not handle gracefully. Got: %q\n", emptyResult)
		passed = false
	}

	if !passed {
		os.Exit(1)
	}

	fmt.Println("All insecure behavior checks passed.")
	os.Exit(0)
}