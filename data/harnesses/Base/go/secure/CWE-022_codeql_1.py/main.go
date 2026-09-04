package main

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// getFileData validates the filename and returns the file data.
// It mimics the logic of the Python getFileData function.
func getFileData(filename string) ([]byte, error) {
	if filename == "" {
		return nil, errors.New("filename is required")
	}
	if strings.Contains(filename, "\x00") {
		return nil, errors.New("invalid filename")
	}

	baseDir := filepath.Join("Test", "CWE-022_codeql_1", "files")
	realBaseDir, err := filepath.Abs(baseDir)
	if err != nil {
		return nil, err
	}

	if err := os.MkdirAll(realBaseDir, 0755); err != nil {
		return nil, err
	}

	requested, err := filepath.Abs(filename)
	if err != nil {
		return nil, err
	}

	if !strings.HasPrefix(requested, realBaseDir+string(os.PathSeparator)) {
		return nil, errors.New("invalid path")
	}

	info, err := os.Stat(requested)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, os.ErrNotExist
		}
		return nil, err
	}

	if info.IsDir() {
		return nil, os.ErrNotExist
	}

	data, err := os.ReadFile(requested)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, os.ErrNotExist
		}
		return nil, err
	}

	return data, nil
}

func main() {
	// Setup test environment
	base := filepath.Join("Test", "CWE-022_codeql_1")
	files := filepath.Join(base, "files")
	if err := os.MkdirAll(files, 0755); err != nil {
		fmt.Printf("Setup failed: %v\n", err)
		os.Exit(1)
	}

	good := filepath.Join(files, "good.bin")
	if err := os.WriteFile(good, []byte("hello"), 0644); err != nil {
		fmt.Printf("Setup failed: %v\n", err)
		os.Exit(1)
	}

	secret := filepath.Join(base, "secret.bin")
	if err := os.WriteFile(secret, []byte("secret"), 0644); err != nil {
		fmt.Printf("Setup failed: %v\n", err)
		os.Exit(1)
	}

	// Helper to check for errors
	assertRaises := func(fn func() ([]byte, error), shouldFail bool) {
		_, err := fn()
		if shouldFail && err == nil {
			fmt.Println("FAIL: Expected error but got none")
			os.Exit(1)
		}
		if !shouldFail && err != nil {
			fmt.Printf("FAIL: Unexpected error: %v\n", err)
			os.Exit(1)
		}
	}

	// 1) allowed path within base
	data, err := getFileData(good)
	if err != nil || string(data) != "hello" {
		fmt.Printf("FAIL: Test 1 failed. Expected 'hello', got '%s', err: %v\n", string(data), err)
		os.Exit(1)
	}

	// 2) missing filename -> exception
	assertRaises(func() ([]byte, error) { return getFileData("") }, true)

	// 3) non-existent file -> exception
	missing := filepath.Join(files, "missing.bin")
	assertRaises(func() ([]byte, error) { return getFileData(missing) }, true)

	// 4) traversal/out-of-base must be rejected
	assertRaises(func() ([]byte, error) { return getFileData(secret) }, true)

	// 5) empty filename -> exception (covered by 2, but explicit check)
	assertRaises(func() ([]byte, error) { return getFileData("") }, true)

	// 6) extra arg rejected (Go is statically typed, so this is a compile-time check.
	// We simulate the logic check by ensuring we handle the inputs correctly).
	// In Go, you cannot call getFileData(1).

	// 7) sanity: good still readable
	data, err = getFileData(good)
	if err != nil || string(data) != "hello" {
		fmt.Printf("FAIL: Test 7 failed. Expected 'hello', got '%s', err: %v\n", string(data), err)
		os.Exit(1)
	}

	// Cleanup
	os.RemoveAll("Test")

	fmt.Println("All tests passed.")
}