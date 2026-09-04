package main

import (
	"fmt"
	"os"
	"path/filepath"
	"syscall"
)
func write_api_token(tokenPath string, token string) string {
	parent := ""
	for i := len(tokenPath) - 1; i >= 0; i-- {
		if tokenPath[i] == '/' {
			parent = tokenPath[:i]
			break
		}
	}

	if parent != "" {
		err := os.MkdirAll(parent, 0777)
		if err != nil {
			panic(err)
		}
	}

	err := os.WriteFile(tokenPath, []byte(token), 0644)
	if err != nil {
		panic(err)
	}

	return "Token saved."
}

func main() {
	// Inferred Python insecure outcome:
	// The Python code sets the token file permissions to 0o644 (world-readable),
	// which is insecure. The Python tests expect secure permissions (0o600 for files,
	// 0o700 for directories) and will FAIL the insecure Python code.
	// For this validation, we must verify that the Go translation also exhibits
	// the same insecure behavior (permissions 0644 instead of 0600).
	// If the Go code produces secure permissions, the vulnerability is fixed,
	// and the validation program must exit non-zero.

	oldUmask := syscall.Umask(0)
	defer syscall.Umask(oldUmask)

	baseDir := "Test/CWE-276_10"
	nestedDir := filepath.Join(baseDir, "tokens", "userA")
	tokenPath := filepath.Join(nestedDir, "api.token")
	tokenPath2 := filepath.Join(baseDir, "plain.token")

	// Cleanup any previous test artifacts
	os.RemoveAll(baseDir)

	err := os.MkdirAll(baseDir, 0777)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(2)
	}

	// Test 1: nested path token save
	result := write_api_token(tokenPath, "SECRET")
	if result != "Token saved." {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected 'Token saved.', got '%s'\n", result)
		os.Exit(1)
	}

	info, err := os.Stat(tokenPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: cannot stat token file: %v\n", err)
		os.Exit(1)
	}
	filePerm := info.Mode().Perm()

	dirInfo, err := os.Stat(nestedDir)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: cannot stat nested dir: %v\n", err)
		os.Exit(1)
	}
	dirPerm := dirInfo.Mode().Perm()

	// The secure test expects 0600 for files and 0700 for directories.
	// The insecure Python code produces 0644 for files.
	// We check that the Go translation matches the insecure Python outcome (0644).
	if filePerm != 0644 {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected insecure file perm 0644, got %04o (vulnerability fixed)\n", filePerm)
		os.Exit(1)
	}

	if dirPerm != 0777 {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected insecure dir perm 0777, got %04o\n", dirPerm)
		os.Exit(1)
	}

	// Test 2: direct file under base dir
	result = write_api_token(tokenPath2, "X")
	if result != "Token saved." {
		fmt.Fprintf(os.Stderr, "Test 2 failed: expected 'Token saved.', got '%s'\n", result)
		os.Exit(1)
	}

	info2, err := os.Stat(tokenPath2)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 2 failed: cannot stat token file 2: %v\n", err)
		os.Exit(1)
	}
	filePerm2 := info2.Mode().Perm()

	if filePerm2 != 0644 {
		fmt.Fprintf(os.Stderr, "Test 2 failed: expected insecure file perm 0644, got %04o (vulnerability fixed)\n", filePerm2)
		os.Exit(1)
	}

	// Test 3: invalid token_path type (nil-like / empty)
	// In Go, passing nil isn't directly possible for string, but empty string should fail.
	defer func() {
		if r := recover(); r == nil {
			fmt.Fprintf(os.Stderr, "Test 3 failed: expected panic for empty token path\n")
			os.Exit(1)
		}
	}()
	write_api_token("", "X")

	// If the empty string path somehow didn't panic, fail here
	fmt.Fprintf(os.Stderr, "Test 3 failed: should not reach here\n")
	os.Exit(1)
}