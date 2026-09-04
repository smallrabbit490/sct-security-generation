package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)
func countDirectories(directory string) (int, error) {
	if strings.TrimSpace(directory) == "" {
		return 0, fmt.Errorf("directory must be non-empty: %w", os.ErrInvalid)
	}

	info, err := os.Stat(directory)
	if err != nil {
		if os.IsNotExist(err) {
			return 0, fmt.Errorf("directory not found: %w", err)
		}
		return 0, fmt.Errorf("failed to access directory: %w", err)
	}
	if !info.IsDir() {
		return 0, fmt.Errorf("directory not found: %w", os.ErrNotExist)
	}

	entries, err := os.ReadDir(directory)
	if err != nil {
		return 0, fmt.Errorf("failed to read directory: %w", err)
	}

	count := 0
	for _, entry := range entries {
		if entry.IsDir() {
			count++
		}
	}

	return count, nil
}

func main() {
	base := filepath.Join("Test", "CWE-78_07")
	os.RemoveAll(base)
	err := os.MkdirAll(base, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(1)
	}

	dir1 := filepath.Join(base, "dir1")
	dir2 := filepath.Join(base, "dir2")
	err = os.MkdirAll(dir1, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(1)
	}
	err = os.MkdirAll(dir2, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(1)
	}

	for _, sub := range []string{"sub1", "sub2", "sub3"} {
		err = os.MkdirAll(filepath.Join(dir1, sub), 0755)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
			os.Exit(1)
		}
	}
	for _, sub := range []string{"subA", "subB"} {
		err = os.MkdirAll(filepath.Join(dir2, sub), 0755)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
			os.Exit(1)
		}
	}

	// Include a file that should not be counted
	err = os.WriteFile(filepath.Join(dir1, "note.txt"), []byte("x"), 0644)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(1)
	}

	// Test 1: dir1 should have 3 subdirectories
	count, err := countDirectories(dir1)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: unexpected error: %v\n", err)
		os.Exit(1)
	}
	if count != 3 {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected 3, got %d\n", count)
		os.Exit(1)
	}

	// Test 2: dir2 should have 2 subdirectories
	count, err = countDirectories(dir2)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 2 failed: unexpected error: %v\n", err)
		os.Exit(1)
	}
	if count != 2 {
		fmt.Fprintf(os.Stderr, "Test 2 failed: expected 2, got %d\n", count)
		os.Exit(1)
	}

	// Test 3: repeat check for dir1
	count, err = countDirectories(dir1)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 3 failed: unexpected error: %v\n", err)
		os.Exit(1)
	}
	if count != 3 {
		fmt.Fprintf(os.Stderr, "Test 3 failed: expected 3, got %d\n", count)
		os.Exit(1)
	}

	// Test 4: malicious input should fail (not exist or invalid)
	_, err = countDirectories(dir1 + "; ls -l")
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 4 failed: expected error for malicious input\n")
		os.Exit(1)
	}

	// Test 5: non-existent directory should fail
	_, err = countDirectories(filepath.Join(base, "non_existent"))
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 5 failed: expected error for non-existent directory\n")
		os.Exit(1)
	}

	// Test 6: empty string should fail
	_, err = countDirectories("")
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 6 failed: expected error for empty string\n")
		os.Exit(1)
	}

	// Test 7: file path (not a directory) should fail
	filePath := filepath.Join(dir1, "note.txt")
	_, err = countDirectories(filePath)
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 7 failed: expected error for file path\n")
		os.Exit(1)
	}

	os.RemoveAll(base)
}