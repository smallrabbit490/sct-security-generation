package main

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
)

// Translated function
func createExecutableFile(data []byte) (string, error) {
	// Check if data is a byte slice (Go equivalent of bytes/bytearray)
	if data == nil {
		return "", errors.New("invalid data type")
	}

	path := "test.bin"
	err := os.WriteFile(path, data, 0600)
	if err != nil {
		return "", err
	}
	if err := os.Chmod(path, 0600); err != nil {
		return "", err
	}

	absPath, err := filepath.Abs(path)
	if err != nil {
		return "", err
	}

	return absPath, nil
}

func main() {
	// Setup test environment
	base := filepath.Join("Test", "CWE-732_author_1")
	err := os.MkdirAll(base, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create test directory: %v\n", err)
		os.Exit(1)
	}

	// Change to test directory
	cwd, err := os.Getwd()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to get working directory: %v\n", err)
		os.Exit(1)
	}
	err = os.Chdir(base)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to change directory: %v\n", err)
		os.Exit(1)
	}

	// Ensure we change back even if tests fail
	defer func() {
		err := os.Chdir(cwd)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Failed to restore working directory: %v\n", err)
			os.Exit(1)
		}
	}()

	// Test 1: Valid input
	p, err := createExecutableFile([]byte{0x00, 0x01})
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: function returned error: %v\n", err)
		os.Exit(1)
	}

	// Check if file exists
	if _, err := os.Stat(p); os.IsNotExist(err) {
		fmt.Fprintf(os.Stderr, "Test 1 failed: file does not exist at path %s\n", p)
		os.Exit(1)
	}

	// Check file permissions (ensure no execute bits)
	info, err := os.Stat(p)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: could not stat file: %v\n", err)
		os.Exit(1)
	}
	mode := info.Mode()
	if mode.Perm()&0111 != 0 {
		fmt.Fprintf(os.Stderr, "Test 1 failed: file has execute permissions (mode: %v)\n", mode)
		os.Exit(1)
	}

	// Check file content
	content, err := os.ReadFile(p)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: could not read file: %v\n", err)
		os.Exit(1)
	}
	if len(content) != 2 || content[0] != 0x00 || content[1] != 0x01 {
		fmt.Fprintf(os.Stderr, "Test 1 failed: file content mismatch: got %v\n", content)
		os.Exit(1)
	}

	// Test 2: Invalid input type (string)
	// Go is statically typed, so we cannot pass a string to a function expecting []byte.
	// However, the Python test checks for TypeError. In Go, this is a compile-time error.
	// We simulate the "invalid data" check by passing nil, which our implementation handles.
	_, err = createExecutableFile(nil)
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 2 failed: expected error for nil data, got nil\n")
		os.Exit(1)
	}

	// Test 3: Insecure Code failure analysis
	// The Python test monkeypatches os.system to raise RuntimeError.
	// In Go, the translated code uses os.WriteFile, not os.system/exec.
	// Therefore, the "Insecure Code" path (executing the file) does not exist in the translated code.
	// The test passes implicitly because the insecure call is not present.

	// If we reach here, all tests passed
	fmt.Println("All tests passed.")
}
