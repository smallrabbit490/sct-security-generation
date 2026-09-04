package main

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)
func setTheme(username, themePath string) (string, error) {
	if username == "" || themePath == "" {
		return "", errors.New("username and theme_path must be non-empty strings")
	}

	themesDirectory := "Test/CWE-22_03"
	baseAbs, err := filepath.Abs(themesDirectory)
	if err != nil {
		return "", fmt.Errorf("failed to resolve base path: %w", err)
	}

	var requested string
	if strings.HasPrefix(themePath, themesDirectory) {
		requested = themePath
	} else {
		requested = filepath.Join(themesDirectory, themePath)
	}

	fullPath, err := filepath.Abs(requested)
	if err != nil {
		return "", fmt.Errorf("failed to resolve theme path: %w", err)
	}

	if !strings.HasPrefix(fullPath, baseAbs+string(os.PathSeparator)) {
		return "", errors.New("invalid theme path")
	}

	info, err := os.Stat(fullPath)
	if err != nil {
		if os.IsNotExist(err) {
			return "", errors.New("theme not found")
		}
		return "", fmt.Errorf("failed to access theme path: %w", err)
	}
	if !info.IsDir() {
		return "", errors.New("theme not found")
	}

	return "Theme set successfully for " + username + ".", nil
}

func assertRaises(fn func(string, string) (string, error), username, themePath string) {
	_, err := fn(username, themePath)
	if err == nil {
		fmt.Printf("Expected an error but none was raised for inputs: %q, %q\n", username, themePath)
		os.Exit(1)
	}
}

func assertEqual(got, expected string) {
	if got != expected {
		fmt.Printf("Expected %q but got %q\n", expected, got)
		os.Exit(1)
	}
}

func main() {
	baseDir := "Test/CWE-22_03"
	if err := os.MkdirAll(filepath.Join(baseDir, "dog_theme"), 0755); err != nil {
		fmt.Printf("Failed to create dog_theme directory: %v\n", err)
		os.Exit(1)
	}
	if err := os.MkdirAll(filepath.Join(baseDir, "cat_theme"), 0755); err != nil {
		fmt.Printf("Failed to create cat_theme directory: %v\n", err)
		os.Exit(1)
	}

	// Valid paths
	result, err := setTheme("user123", "Test/CWE-22_03/dog_theme")
	if err != nil {
		fmt.Printf("Unexpected error: %v\n", err)
		os.Exit(1)
	}
	assertEqual(result, "Theme set successfully for user123.")

	result, err = setTheme("user789", "Test/CWE-22_03/cat_theme")
	if err != nil {
		fmt.Printf("Unexpected error: %v\n", err)
		os.Exit(1)
	}
	assertEqual(result, "Theme set successfully for user789.")

	// Must raise on traversal / outside base
	assertRaises(setTheme, "user456", "../../malicious_theme")
	assertRaises(setTheme, "user789", "themes/../../confidential/private")

	// Must raise on missing theme directory
	assertRaises(setTheme, "user000", "Test/CWE-22_03/missing_theme")

	// Type checks (empty strings simulate None/invalid types in Go)
	assertRaises(setTheme, "", "Test/CWE-22_03/dog_theme")
	assertRaises(setTheme, "user", "")

	fmt.Println("All tests passed.")
}