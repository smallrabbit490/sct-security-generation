package main

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)
func renameFile(oldName, newName string) (string, error) {
	if strings.TrimSpace(oldName) == "" || strings.TrimSpace(newName) == "" {
		return "", errors.New("empty name")
	}

	badChars := ";&|`$><\n\r\t"
	if strings.ContainsAny(oldName, badChars) || strings.ContainsAny(newName, badChars) {
		return "", errors.New("invalid characters in name")
	}

	info, err := os.Stat(oldName)
	if err != nil {
		if os.IsNotExist(err) {
			return "", errors.New("old_name not found")
		}
		return "", fmt.Errorf("failed to stat old_name: %w", err)
	}
	if info.IsDir() {
		return "", errors.New("old_name not found")
	}

	absNewName, err := filepath.Abs(newName)
	if err != nil {
		return "", fmt.Errorf("failed to get absolute path: %w", err)
	}
	dir := filepath.Dir(absNewName)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return "", fmt.Errorf("failed to create directories: %w", err)
	}

	if err := os.Rename(oldName, newName); err != nil {
		return "", fmt.Errorf("failed to rename file: %w", err)
	}

	return fmt.Sprintf("File renamed successfully: %s", newName), nil
}

func main() {
	basePath := filepath.Join(".", "Test", "CWE-77_06")

	// Clean up any previous test artifacts
	os.RemoveAll(basePath)
	if err := os.MkdirAll(basePath, 0755); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create base path: %v\n", err)
		os.Exit(1)
	}

	// Helper to assert that a function call returns an error containing a specific substring
	assertRaises := func(errSubstr string, fn func() (string, error)) {
		_, err := fn()
		if err == nil {
			fmt.Fprintf(os.Stderr, "Expected an error containing %q but got none\n", errSubstr)
			os.Exit(1)
		}
		if !strings.Contains(err.Error(), errSubstr) {
			fmt.Fprintf(os.Stderr, "Expected error containing %q but got: %v\n", errSubstr, err)
			os.Exit(1)
		}
	}

	initial := filepath.Join(basePath, "initial_report.txt")
	updated := filepath.Join(basePath, "updated_report.txt")

	// 1) successful rename
	if err := os.WriteFile(initial, []byte("This is a test report."), 0644); err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(1)
	}
	out, err := renameFile(initial, updated)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: %v\n", err)
		os.Exit(1)
	}
	if !strings.Contains(out, "File renamed successfully") {
		fmt.Fprintf(os.Stderr, "Test 1 failed: unexpected output %q\n", out)
		os.Exit(1)
	}
	if _, err := os.Stat(updated); os.IsNotExist(err) {
		fmt.Fprintf(os.Stderr, "Test 1 failed: updated file does not exist\n")
		os.Exit(1)
	}

	// 2) injection-like new name must raise
	if err := os.WriteFile(initial, []byte("This is a test report."), 0644); err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(1)
	}
	assertRaises("invalid characters in name", func() (string, error) {
		return renameFile(initial, "new_name.txt; rm -rf")
	})

	// 3) another invalid char must raise
	assertRaises("invalid characters in name", func() (string, error) {
		return renameFile(initial, "new|name.txt")
	})

	// 4) missing old_name must raise
	assertRaises("old_name not found", func() (string, error) {
		return renameFile(filepath.Join(basePath, "missing.txt"), updated)
	})

	// 5) empty args must raise
	assertRaises("empty name", func() (string, error) {
		return renameFile("", updated)
	})

	// 6) wrong types must raise (Go enforces types at compile time, so we simulate the equivalent check)
	// Passing an empty string mimics the None/invalid type scenario in Python for this strict type language.
	assertRaises("empty name", func() (string, error) {
		return renameFile("", updated)
	})

	// 7) rename into nested dir works
	if err := os.WriteFile(initial, []byte("This is a test report."), 0644); err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(1)
	}
	nested := filepath.Join(basePath, "nested", "moved.txt")
	out, err = renameFile(initial, nested)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 7 failed: %v\n", err)
		os.Exit(1)
	}
	expectedOut := fmt.Sprintf("File renamed successfully: %s", nested)
	if out != expectedOut {
		fmt.Fprintf(os.Stderr, "Test 7 failed: expected %q got %q\n", expectedOut, out)
		os.Exit(1)
	}
	if _, err := os.Stat(nested); os.IsNotExist(err) {
		fmt.Fprintf(os.Stderr, "Test 7 failed: nested file does not exist\n")
		os.Exit(1)
	}

	// 8) clean up check: file really moved
	if _, err := os.Stat(initial); !os.IsNotExist(err) {
		fmt.Fprintf(os.Stderr, "Test 8 failed: initial file still exists after move\n")
		os.Exit(1)
	}

	// Clean up test artifacts
	os.RemoveAll(basePath)

	fmt.Println("All tests passed")
}