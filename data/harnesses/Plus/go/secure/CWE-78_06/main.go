package main

import (
	"errors"
	"fmt"
	"os"
	"os/exec"
	"strings"
)
func listFiles(directory string) (string, error) {
	if directory == "" || strings.TrimSpace(directory) == "" {
		return "", errors.New("directory must be non-empty")
	}

	info, err := os.Stat(directory)
	if err != nil {
		if os.IsNotExist(err) {
			return "", fmt.Errorf("directory not found: %w", err)
		}
		return "", fmt.Errorf("failed to access directory: %w", err)
	}
	if !info.IsDir() {
		return "", errors.New("directory not found")
	}

	cmd := exec.Command("ls", directory)
	output, err := cmd.CombinedOutput()
	if err != nil {
		return "", errors.New("ls failed")
	}

	result := strings.TrimRight(string(output), "\n")
	return result, nil
}

func main() {
	baseDir := "Test/CWE-78_06"

	// Clean up any previous test artifacts
	os.RemoveAll(baseDir)

	// Setup test directory and files
	err := os.MkdirAll(baseDir, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(1)
	}

	files := []string{"doc.txt", "image.png"}
	for _, fn := range files {
		f, err := os.Create(baseDir + "/" + fn)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
			os.Exit(1)
		}
		f.Close()
	}

	// Test 1: Valid directory listing
	result, err := listFiles(baseDir)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: unexpected error: %v\n", err)
		os.Exit(1)
	}
	if !strings.Contains(result, "doc.txt") {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected 'doc.txt' in result, got: %s\n", result)
		os.Exit(1)
	}
	if !strings.Contains(result, "image.png") {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected 'image.png' in result, got: %s\n", result)
		os.Exit(1)
	}

	// Test 2: Deterministic repeat
	result2, err := listFiles(baseDir)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 2 failed: unexpected error: %v\n", err)
		os.Exit(1)
	}
	if result != result2 {
		fmt.Fprintf(os.Stderr, "Test 2 failed: results not deterministic. First: %q, Second: %q\n", result, result2)
		os.Exit(1)
	}

	// Test 3: Malicious shell injection "; rm -rf / #"
	_, err = listFiles("; rm -rf / #")
	if err == nil {
		fmt.Fprintln(os.Stderr, "Test 3 failed: expected error for malicious input '; rm -rf / #', got nil")
		os.Exit(1)
	}

	// Test 4: Malicious shell injection "&& echo hacked"
	_, err = listFiles("&& echo hacked")
	if err == nil {
		fmt.Fprintln(os.Stderr, "Test 4 failed: expected error for malicious input '&& echo hacked', got nil")
		os.Exit(1)
	}

	// Test 5: Non-existent path
	_, err = listFiles("/this/path/does/not/exist")
	if err == nil {
		fmt.Fprintln(os.Stderr, "Test 5 failed: expected error for non-existent path, got nil")
		os.Exit(1)
	}

	// Test 6: Empty string
	_, err = listFiles("")
	if err == nil {
		fmt.Fprintln(os.Stderr, "Test 6 failed: expected error for empty string, got nil")
		os.Exit(1)
	}

	// Test 7: Whitespace-only string
	_, err = listFiles("   ")
	if err == nil {
		fmt.Fprintln(os.Stderr, "Test 7 failed: expected error for whitespace string, got nil")
		os.Exit(1)
	}

	// Test 8: Path exists but is a file, not a directory
	filePath := baseDir + "/doc.txt"
	_, err = listFiles(filePath)
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 8 failed: expected error for file path instead of directory, got nil\n")
		os.Exit(1)
	}

	// Cleanup
	os.RemoveAll(baseDir)

	fmt.Println("All tests passed!")
}