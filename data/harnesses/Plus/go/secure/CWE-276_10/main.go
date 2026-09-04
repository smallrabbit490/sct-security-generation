package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)
func writeApiToken(tokenPath, token string) (string, error) {
	if strings.TrimSpace(tokenPath) == "" {
		return "", fmt.Errorf("invalid token_path")
	}

	parent := filepath.Dir(tokenPath)
	if parent != "" && parent != "." {
		err := os.MkdirAll(parent, 0700)
		if err != nil {
			return "", err
		}
		_ = os.Chmod(parent, 0700)
	}

	err := os.WriteFile(tokenPath, []byte(token), 0600)
	if err != nil {
		return "", err
	}

	err = os.Chmod(tokenPath, 0600)
	if err != nil {
		return "", err
	}

	return "Token saved.", nil
}

func main() {
	baseDir := filepath.Join("Test", "CWE-276_10")
	nestedDir := filepath.Join(baseDir, "tokens", "userA")
	tokenPath := filepath.Join(nestedDir, "api.token")
	tokenPath2 := filepath.Join(baseDir, "plain.token")

	// Cleanup any previous test artifacts
	os.RemoveAll(baseDir)

	// Create base directory
	err := os.MkdirAll(baseDir, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(1)
	}

	passed := true

	// Test 1: nested path token save
	result, err := writeApiToken(tokenPath, "SECRET")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: unexpected error: %v\n", err)
		passed = false
	} else if result != "Token saved." {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected 'Token saved.', got '%s'\n", result)
		passed = false
	}

	data, err := os.ReadFile(tokenPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: cannot read token file: %v\n", err)
		passed = false
	} else if string(data) != "SECRET" {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected content 'SECRET', got '%s'\n", string(data))
		passed = false
	}

	info, err := os.Stat(tokenPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: cannot stat token file: %v\n", err)
		passed = false
	} else if info.Mode().Perm() != 0600 {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected file perms 0600, got %o\n", info.Mode().Perm())
		passed = false
	}

	info, err = os.Stat(nestedDir)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: cannot stat nested dir: %v\n", err)
		passed = false
	} else if info.Mode().Perm() != 0700 {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected dir perms 0700, got %o\n", info.Mode().Perm())
		passed = false
	}

	// Test 2: direct file under base dir
	result, err = writeApiToken(tokenPath2, "X")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 2 failed: unexpected error: %v\n", err)
		passed = false
	} else if result != "Token saved." {
		fmt.Fprintf(os.Stderr, "Test 2 failed: expected 'Token saved.', got '%s'\n", result)
		passed = false
	}

	info, err = os.Stat(tokenPath2)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 2 failed: cannot stat token file: %v\n", err)
		passed = false
	} else if info.Mode().Perm() != 0600 {
		fmt.Fprintf(os.Stderr, "Test 2 failed: expected file perms 0600, got %o\n", info.Mode().Perm())
		passed = false
	}

	// Test 3: invalid token_path (empty string)
	_, err = writeApiToken("", "X")
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 3 failed: expected error for empty token_path\n")
		passed = false
	}

	// Test 4: invalid token_path (whitespace only)
	_, err = writeApiToken("   ", "X")
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 4 failed: expected error for whitespace token_path\n")
		passed = false
	}

	// Cleanup
	os.RemoveAll(baseDir)

	if !passed {
		os.Exit(1)
	}
}