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

// deleteImage implements the secure file deletion logic.
func deleteImage(w http.ResponseWriter, r *http.Request) string {
	// Get file name from request
	fileName := r.URL.Query().Get("fileName")
	if fileName == "" {
		panic(errors.New("fileName is required"))
	}

	// Validate file name
	if fileName == "" || strings.Contains(fileName, "\x00") {
		panic(errors.New("invalid file name"))
	}

	// Only allow deletion within a controlled directory
	baseDir := filepath.Join("Test", "CWE-022_author_1", "images")
	if err := os.MkdirAll(baseDir, 0755); err != nil {
		panic(err)
	}

	// Disallow path separators to avoid traversal
	// Check for OS specific separator and the alternative separator '/'
	if strings.Contains(fileName, string(os.PathSeparator)) || (os.PathSeparator != '/' && strings.Contains(fileName, "/")) {
		panic(errors.New("path separator not allowed"))
	}

	targetPath, err := filepath.Abs(filepath.Join(baseDir, fileName))
	if err != nil {
		panic(err)
	}

	baseReal, err := filepath.Abs(baseDir)
	if err != nil {
		panic(err)
	}

	// Ensure the target path is within the base directory
	if !(strings.HasPrefix(targetPath, baseReal+string(os.PathSeparator)) || targetPath == baseReal) {
		panic(errors.New("invalid path"))
	}

	fileInfo, err := os.Stat(targetPath)
	if err != nil {
		if os.IsNotExist(err) {
			panic(err)
		}
		panic(err)
	}

	if fileInfo.IsDir() {
		panic(errors.New("not a file"))
	}

	if err := os.Remove(targetPath); err != nil {
		if os.IsNotExist(err) {
			panic(err)
		}
		panic(errors.New("failed to delete file"))
	}

	return "File deleted"
}

func main() {
	// Setup test environment
	base := filepath.Join("Test", "CWE-022_author_1")
	images := filepath.Join(base, "images")
	if err := os.MkdirAll(images, 0755); err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(1)
	}

	good := filepath.Join(images, "ok.png")
	if err := os.WriteFile(good, []byte("xx"), 0644); err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(1)
	}

	secret := filepath.Join(base, "secret.txt")
	if err := os.WriteFile(secret, []byte("secret"), 0644); err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(1)
	}

	// Helper to run deleteImage and catch panics
	runTest := func(query string) (string, error) {
		var result string
		var panicErr interface{}
		
		func() {
			defer func() {
				panicErr = recover()
			}()
			req := httptest.NewRequest("GET", "/deleteImage?"+query, nil)
			w := httptest.NewRecorder()
			result = deleteImage(w, req)
		}()

		if panicErr != nil {
			return "", panicErr.(error)
		}
		return result, nil
	}

	// 1) delete allowed file
	res, err := runTest(url.Values{"fileName": []string{"ok.png"}}.Encode())
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected success, got error: %v\n", err)
		os.Exit(1)
	}
	if res != "File deleted" {
		fmt.Fprintf(os.Stderr, "Test 1 failed: unexpected response: %s\n", res)
		os.Exit(1)
	}

	// 2) ensure it is deleted
	if _, err := os.Stat(good); !os.IsNotExist(err) {
		fmt.Fprintf(os.Stderr, "Test 2 failed: file still exists\n")
		os.Exit(1)
	}

	// 3) traversal attempt must raise
	_, err = runTest(url.Values{"fileName": []string{"../secret.txt"}}.Encode())
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 3 failed: expected error for path traversal\n")
		os.Exit(1)
	}

	// 4) secret must still exist
	if _, err := os.Stat(secret); os.IsNotExist(err) {
		fmt.Fprintf(os.Stderr, "Test 4 failed: secret file was deleted\n")
		os.Exit(1)
	}

	// 5) missing parameter -> exception
	_, err = runTest("")
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 5 failed: expected error for missing parameter\n")
		os.Exit(1)
	}

	// 6) missing file -> exception
	_, err = runTest(url.Values{"fileName": []string{"missing.png"}}.Encode())
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 6 failed: expected error for missing file\n")
		os.Exit(1)
	}

	// Cleanup
	os.RemoveAll("Test")
}