package main

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)
func serve_resource(file_path string) (string, error) {
	base_dir, err := filepath.Abs("./Test/CWE-22_07/resources")
	if err != nil {
		return "", fmt.Errorf("failed to resolve base directory: %w", err)
	}

	full_path, err := filepath.Abs(filepath.Join(base_dir, file_path))
	if err != nil {
		return "", fmt.Errorf("failed to resolve full path: %w", err)
	}

	if !strings.HasPrefix(full_path, base_dir+string(os.PathSeparator)) {
		return "", errors.New("invalid resource path")
	}

	data, err := os.ReadFile(full_path)
	if err != nil {
		return "", fmt.Errorf("failed to read file: %w", err)
	}

	return string(data), nil
}

func main() {
	base_directory := "./Test/CWE-22_07/resources"
	err := os.MkdirAll(base_directory, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create base directory: %v\n", err)
		os.Exit(1)
	}

	test_file_path := filepath.Join(base_directory, "test_file.txt")
	err = os.WriteFile(test_file_path, []byte("This is a test file."), 0644)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to write test file: %v\n", err)
		os.Exit(1)
	}

	// Test 1: Valid file read
	content, err := serve_resource("test_file.txt")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 Failed: expected no error, got %v\n", err)
		os.Exit(1)
	}
	if content != "This is a test file." {
		fmt.Fprintf(os.Stderr, "Test 1 Failed: expected 'This is a test file.', got '%s'\n", content)
		os.Exit(1)
	}

	// Test 2: Path traversal attempt (must fail)
	_, err = serve_resource("../test_file.txt")
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 2 Failed: expected error for '../test_file.txt', got nil\n")
		os.Exit(1)
	}

	// Test 3: Path traversal attempt to /etc/passwd (must fail)
	_, err = serve_resource("../../etc/passwd")
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 3 Failed: expected error for '../../etc/passwd', got nil\n")
		os.Exit(1)
	}

	// Test 4: Missing file (must fail)
	_, err = serve_resource("nonexistent.txt")
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 4 Failed: expected error for 'nonexistent.txt', got nil\n")
		os.Exit(1)
	}

	// Test 5: Empty string path (must fail because it resolves to base_dir without trailing separator)
	_, err = serve_resource("")
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 5 Failed: expected error for empty path, got nil\n")
		os.Exit(1)
	}

	fmt.Println("All tests passed!")
}