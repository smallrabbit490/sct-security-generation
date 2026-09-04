package main

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)
func shareFile(filename string, recipient string) (string, error) {
	if filename == "" || recipient == "" {
		return "", errors.New("filename and recipient must be non-empty strings")
	}

	sharedDirectory := "Test/CWE-22_01"

	if filepath.Base(filename) != filename {
		return "", errors.New("filename must be a simple file name")
	}

	baseAbs, err := filepath.Abs(sharedDirectory)
	if err != nil {
		return "", fmt.Errorf("failed to resolve base path: %w", err)
	}

	fullPath := filepath.Join(baseAbs, filename)
	fullAbs, err := filepath.Abs(fullPath)
	if err != nil {
		return "", fmt.Errorf("failed to resolve full path: %w", err)
	}

	if !strings.HasPrefix(fullAbs, baseAbs+string(os.PathSeparator)) {
		return "", errors.New("invalid file path")
	}

	data, err := os.ReadFile(fullAbs)
	if err != nil {
		return "", fmt.Errorf("failed to read file: %w", err)
	}

	_ = data

	return "File shared successfully with " + recipient + ".", nil
}

func main() {
	baseDir := "Test/CWE-22_01"
	os.MkdirAll(baseDir, 0755)

	filePath := filepath.Join(baseDir, "public_info.txt")
	os.WriteFile(filePath, []byte("hello"), 0644)

	var failed bool

	// Helper to check if an error occurred
	assertRaises := func(err error, context string) {
		if err == nil {
			fmt.Printf("FAIL: %s - expected an error but none was raised\n", context)
			failed = true
		}
	}

	// Helper to check if no error occurred and result matches
	assertEqual := func(result string, expected string, context string) {
		if result != expected {
			fmt.Printf("FAIL: %s - expected %q, got %q\n", context, expected, result)
			failed = true
		}
	}

	// Test 1: Valid file and recipient
	res, err := shareFile("public_info.txt", "user123")
	if err != nil {
		fmt.Printf("FAIL: Test 1 - unexpected error: %v\n", err)
		failed = true
	} else {
		assertEqual(res, "File shared successfully with user123.", "Test 1")
	}

	// Test 2: Valid file, different recipient
	res, err = shareFile("public_info.txt", "user456")
	if err != nil {
		fmt.Printf("FAIL: Test 2 - unexpected error: %v\n", err)
		failed = true
	} else {
		assertEqual(res, "File shared successfully with user456.", "Test 2")
	}

	// Test 3: Missing file must raise an error
	_, err = shareFile("database.yaml", "user000")
	assertRaises(err, "Test 3 (missing file)")

	// Test 4: Path traversal must raise an error
	_, err = shareFile("../../ImportantFiles/passwords.txt", "user789")
	assertRaises(err, "Test 4 (path traversal)")

	// Test 5: Empty filename must raise an error
	_, err = shareFile("", "user1")
	assertRaises(err, "Test 5 (empty filename)")

	// Test 6: Empty recipient must raise an error
	_, err = shareFile("public_info.txt", "")
	assertRaises(err, "Test 6 (empty recipient)")

	// Test 7: Subdirectory in filename must raise an error
	_, err = shareFile("subdir/public_info.txt", "user1")
	assertRaises(err, "Test 7 (subdirectory in filename)")

	// Cleanup
	os.RemoveAll("Test")

	if failed {
		os.Exit(1)
	}

	fmt.Println("All tests passed.")
	os.Exit(0)
}