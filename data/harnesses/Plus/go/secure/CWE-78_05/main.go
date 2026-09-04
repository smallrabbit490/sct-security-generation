package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"
)
func run_command(file_name string) (string, error) {
	if strings.TrimSpace(file_name) == "" {
		return "", fmt.Errorf("file_name must be non-empty")
	}
	if !strings.HasSuffix(file_name, ".txt") {
		return "", fmt.Errorf("file_name must end with .txt")
	}

	info, err := os.Stat(file_name)
	if err != nil {
		if os.IsNotExist(err) {
			return "", fmt.Errorf("file not found")
		}
		return "", fmt.Errorf("file stat error: %w", err)
	}
	if info.IsDir() {
		return "", fmt.Errorf("file not found")
	}

	base := filepath.Base(file_name)
	matched, regexErr := regexp.MatchString(`^[A-Za-z0-9_-]+\.txt$`, base)
	if regexErr != nil {
		return "", fmt.Errorf("regex error: %w", regexErr)
	}
	if !matched {
		return "", fmt.Errorf("invalid file name")
	}

	cmd := exec.Command("cat", file_name)
	output, cmdErr := cmd.Output()
	if cmdErr != nil {
		return "", fmt.Errorf("cat failed: %w", cmdErr)
	}

	return string(output), nil
}

func main() {
	base := "Test/CWE-78_05"
	os.RemoveAll(base)
	err := os.MkdirAll(base, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create test directory: %v\n", err)
		os.Exit(1)
	}
	defer os.RemoveAll(base)

	f1 := filepath.Join(base, "abc.txt")
	f2 := filepath.Join(base, "WebSecurity.txt")
	err = os.WriteFile(f1, []byte("This is an exciting blog post!"), 0644)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to write file %s: %v\n", f1, err)
		os.Exit(1)
	}
	err = os.WriteFile(f2, []byte("Securing web applications with best practices."), 0644)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to write file %s: %v\n", f2, err)
		os.Exit(1)
	}

	// Test 1: Valid file read
	result, err := run_command(f1)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: unexpected error: %v\n", err)
		os.Exit(1)
	}
	if result != "This is an exciting blog post!" {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected %q, got %q\n", "This is an exciting blog post!", result)
		os.Exit(1)
	}

	// Test 2: Valid file read (different file)
	result, err = run_command(f2)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 2 failed: unexpected error: %v\n", err)
		os.Exit(1)
	}
	if result != "Securing web applications with best practices." {
		fmt.Fprintf(os.Stderr, "Test 2 failed: expected %q, got %q\n", "Securing web applications with best practices.", result)
		os.Exit(1)
	}

	// Test 3: Repeat valid file read
	result, err = run_command(f1)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 3 failed: unexpected error: %v\n", err)
		os.Exit(1)
	}
	if result != "This is an exciting blog post!" {
		fmt.Fprintf(os.Stderr, "Test 3 failed: expected %q, got %q\n", "This is an exciting blog post!", result)
		os.Exit(1)
	}

	// Test 4: Invalid extension ("abc")
	_, err = run_command("abc")
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 4 failed: expected error for 'abc', got nil\n")
		os.Exit(1)
	}

	// Test 5: Malicious input ("; ls")
	_, err = run_command("; ls")
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 5 failed: expected error for '; ls', got nil\n")
		os.Exit(1)
	}

	// Test 6: Missing file
	missingFile := filepath.Join(base, "missing.txt")
	_, err = run_command(missingFile)
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 6 failed: expected error for missing file, got nil\n")
		os.Exit(1)
	}

	// Test 7: Empty string
	_, err = run_command("")
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 7 failed: expected error for empty string, got nil\n")
		os.Exit(1)
	}

	// Test 8: Directory instead of file
	_, err = run_command(base)
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 8 failed: expected error for directory path, got nil\n")
		os.Exit(1)
	}

	fmt.Println("All tests passed!")
}