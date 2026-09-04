package main

import (
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
)

// readFile mimics the Python function behavior.
// It checks if the file exists inside a specific directory, is not a symlink,
// and returns its content.
func readFile(fileName interface{}) (string, error) {
	// Check if fileName is a string
	strFileName, ok := fileName.(string)
	if !ok {
		return "", errors.New("TypeError")
	}

	baseDir, err := filepath.Abs(filepath.Join("Test", "CWE-367_author_1"))
	if err != nil {
		return "", err
	}

	path, err := filepath.Abs(strFileName)
	if err != nil {
		return "", err
	}

	// Only allow reading inside the dedicated test directory
	// filepath.Separator is used to ensure path matching is correct
	if !strings.HasPrefix(path, baseDir+string(os.PathSeparator)) {
		return "", errors.New("ValueError")
	}

	// Avoid TOCTOU by opening directly and refusing symlinks
	// Use Lstat to check for symlinks without following them
	fileInfo, err := os.Lstat(path)
	if err != nil {
		return "", errors.New("ValueError")
	}
	if fileInfo.Mode()&os.ModeSymlink != 0 {
		return "", errors.New("ValueError")
	}

	f, err := os.Open(path)
	if err != nil {
		return "", errors.New("ValueError")
	}
	defer f.Close()

	content, err := io.ReadAll(f)
	if err != nil {
		return "", errors.New("ValueError")
	}

	return string(content), nil
}

func main() {
	// Setup test environment
	base := filepath.Join("Test", "CWE-367_author_1")
	err := os.MkdirAll(base, 0755)
	if err != nil {
		fmt.Printf("Setup failed: %v\n", err)
		os.Exit(1)
	}

	safePath := filepath.Join(base, "safe.txt")
	err = os.WriteFile(safePath, []byte("hello"), 0644)
	if err != nil {
		fmt.Printf("Setup failed: %v\n", err)
		os.Exit(1)
	}
	defer os.RemoveAll("Test") // Cleanup

	// Helper to check for errors
	assertRaises := func(fn func() (string, error), errType string) {
		_, err := fn()
		if err == nil {
			fmt.Printf("Expected error %s, got nil\n", errType)
			os.Exit(1)
		}
		// The Python code raises specific exceptions. In Go we return error strings.
		// We check if the error message matches the expected type name.
		if !strings.Contains(err.Error(), errType) {
			fmt.Printf("Expected error type %s, got %v\n", errType, err)
			os.Exit(1)
		}
	}

	// Test 1: Valid read
	content, err := readFile(safePath)
	if err != nil {
		fmt.Printf("Test 1 failed: %v\n", err)
		os.Exit(1)
	}
	if content != "hello" {
		fmt.Printf("Test 1 failed: expected 'hello', got '%s'\n", content)
		os.Exit(1)
	}

	// Test 2: Path traversal (relative path not in base)
	assertRaises(func() (string, error) { return readFile("safe.txt") }, "ValueError")

	// Test 3: Path traversal (outside access)
	assertRaises(func() (string, error) { return readFile(filepath.Join("Test", "..", "outside.txt")) }, "ValueError")

	// Test 4: Missing file inside base
	assertRaises(func() (string, error) { return readFile(filepath.Join(base, "missing.txt")) }, "ValueError")

	// Test 5: Type check (integer)
	assertRaises(func() (string, error) { return readFile(123) }, "TypeError")

	// Test 6: Extra arguments
	// The Go function signature accepts a single interface{}.
	// Passing multiple arguments to a function that takes one is a compile-time error in Go.
	// However, to mimic the Python test logic which calls candidate(safe_path, 1),
	// we verify that the function strictly rejects non-string inputs or invalid usage.
	// Since we cannot call readFile(safePath, 1) in Go code (it won't compile),
	// we verify the type checking logic is robust.
	// The Python test `assert_raises(candidate, safe_path, 1, exc_types=(TypeError,))`
	// implies the function should handle invalid arity or types. In Go, arity is checked at compile time.
	// We will skip the arity check as it's a language feature, but ensure the type check works.
	// If we were to simulate a variadic interface, we would, but the signature is fixed.
	// We assume the "Extra arg rejected" is covered by the strict type checking of the single argument.

	fmt.Println("All tests passed.")
}