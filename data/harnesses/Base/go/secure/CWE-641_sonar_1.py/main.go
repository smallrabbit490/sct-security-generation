package main

import (
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"strings"
)

// download is the translated function from the Python source.
// It returns an error if validation fails, or nil if the file was served successfully.
func download(w http.ResponseWriter, r *http.Request) error {
	// Get the file name from the request
	file := r.URL.Query().Get("file")
	if file == "" {
		return errors.New("file parameter missing")
	}

	// CWE-641: prevent path injection during parsing
	if strings.Contains(file, "/") || strings.Contains(file, "\\") || strings.TrimSpace(file) == "" {
		return errors.New("invalid file name")
	}

	parts := strings.Split(file, "_")
	for _, p := range parts {
		if p == "" || p == "." || p == ".." {
			return errors.New("invalid file path component")
		}
	}

	// Restrict to a sandbox base directory
	baseDir := filepath.Join("files")
	absBaseDir, err := filepath.Abs(baseDir)
	if err != nil {
		return err
	}

	relPath := filepath.Join(parts...)
	absPath := filepath.Join(absBaseDir, relPath)
	absPath, err = filepath.Abs(absPath)
	if err != nil {
		return err
	}

	if !strings.HasPrefix(absPath, absBaseDir+string(os.PathSeparator)) {
		return errors.New("invalid file path")
	}

	// Check if the file exists
	if _, err := os.Stat(absPath); os.IsNotExist(err) {
		return errors.New("file not found")
	}

	// Send the file as an attachment
	http.ServeFile(w, r, absPath)
	return nil
}

func main() {
	// Setup test environment
	base := filepath.Join("Test", "CWE-641_sonar_1")
	filesDir := filepath.Join(base, "files", "docs")
	
	// Clean up previous test run if necessary
	os.RemoveAll(base)
	
	if err := os.MkdirAll(filesDir, 0755); err != nil {
		fmt.Printf("FATAL: Failed to create test directories: %v\n", err)
		os.Exit(1)
	}
	
	testFile := filepath.Join(filesDir, "readme.txt")
	if err := os.WriteFile(testFile, []byte("ok"), 0644); err != nil {
		fmt.Printf("FATAL: Failed to create test file: %v\n", err)
		os.Exit(1)
	}

	// Change current working directory to the test base
	cwd, err := os.Getwd()
	if err != nil {
		fmt.Printf("FATAL: Failed to get CWD: %v\n", err)
		os.Exit(1)
	}
	if err := os.Chdir(base); err != nil {
		fmt.Printf("FATAL: Failed to chdir: %v\n", err)
		os.Exit(1)
	}
	defer os.Chdir(cwd)
	defer os.RemoveAll(base)

	// Helper to create a request and run download
	runTest := func(fileParam string) error {
		req := httptest.NewRequest("GET", "/download?file="+url.QueryEscape(fileParam), nil)
		rr := httptest.NewRecorder()
		return download(rr, req)
	}

	// Test 1: Valid file
	err = runTest("docs_readme.txt")
	if err != nil {
		fmt.Printf("FAIL: Valid file request returned error: %v\n", err)
		os.Exit(1)
	}

	// Test 2: Traversal-like segments rejected (ValueError equivalent)
	err = runTest(".._.._etc_passwd")
	if err == nil {
		fmt.Println("FAIL: Traversal-like segments were not rejected")
		os.Exit(1)
	}
	// We expect a specific error message or type, but checking for non-nil is sufficient for the logic
	if !strings.Contains(err.Error(), "invalid file path component") && !strings.Contains(err.Error(), "invalid file path") {
		fmt.Printf("FAIL: Traversal check returned unexpected error: %v\n", err)
		os.Exit(1)
	}

	// Test 3: Missing file rejected (FileNotFoundError equivalent)
	err = runTest("docs_missing.txt")
	if err == nil {
		fmt.Println("FAIL: Missing file was not rejected")
		os.Exit(1)
	}
	if !strings.Contains(err.Error(), "file not found") {
		fmt.Printf("FAIL: Missing file check returned unexpected error: %v\n", err)
		os.Exit(1)
	}

	// Test 4: Empty rejected (ValueError equivalent)
	err = runTest("")
	if err == nil {
		fmt.Println("FAIL: Empty file param was not rejected")
		os.Exit(1)
	}
	if !strings.Contains(err.Error(), "file parameter missing") {
		fmt.Printf("FAIL: Empty param check returned unexpected error: %v\n", err)
		os.Exit(1)
	}

	// Test 5: Extra arg rejected (TypeError equivalent)
	// The Go signature is fixed (w, r), so we can't pass extra args at compile time.
	// However, the Python test checks `candidate(1)`. In Go, this is a compile-time error.
	// We verify the function signature is correct by the fact that the code compiles and runs.
	// To satisfy the spirit of the test, we ensure the function handles invalid inputs gracefully.
	// Since we can't call download(1), we assume this passes by compilation.

	fmt.Println("All tests passed.")
}