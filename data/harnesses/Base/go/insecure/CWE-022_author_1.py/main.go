package main

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
)

func deleteImage(w http.ResponseWriter, r *http.Request) {
	fileName := r.URL.Query().Get("fileName")
	os.Remove(fileName)
	w.Write([]byte("File deleted"))
}

func main() {
	base, err := os.MkdirTemp("", "CWE-022")
	if err != nil {
		fmt.Fprintf(os.Stderr, "FAIL: could not create temp dir: %v\n", err)
		os.Exit(1)
	}
	defer os.RemoveAll(base)

	imagesDir := filepath.Join(base, "images")
	if err := os.Mkdir(imagesDir, 0755); err != nil {
		fmt.Fprintf(os.Stderr, "FAIL: could not create images dir: %v\n", err)
		os.Exit(1)
	}

	goodFile := filepath.Join(imagesDir, "ok.png")
	if err := os.WriteFile(goodFile, []byte("xx"), 0644); err != nil {
		fmt.Fprintf(os.Stderr, "FAIL: could not create ok.png: %v\n", err)
		os.Exit(1)
	}

	secretFile := filepath.Join(base, "secret.txt")
	if err := os.WriteFile(secretFile, []byte("secret"), 0644); err != nil {
		fmt.Fprintf(os.Stderr, "FAIL: could not create secret.txt: %v\n", err)
		os.Exit(1)
	}

	// Test 1: Delete allowed file
	req1 := httptest.NewRequest("GET", "/deleteImage?fileName=ok.png", nil)
	rr1 := httptest.NewRecorder()

	// The insecure Go code uses os.Remove(fileName) directly.
	// Since fileName is just "ok.png" (no path), os.Remove will look in the
	// current working directory (which is the temp base dir we set below).
	// To make the insecure code successfully delete the file, we must be in
	// the images directory.
	originalDir, _ := os.Getwd()
	os.Chdir(imagesDir)
	deleteImage(rr1, req1)
	os.Chdir(originalDir)

	if rr1.Code != http.StatusOK {
		fmt.Fprintf(os.Stderr, "FAIL: expected status 200, got %d\n", rr1.Code)
		os.Exit(1)
	}
	if !strings.Contains(rr1.Body.String(), "File deleted") {
		fmt.Fprintf(os.Stderr, "FAIL: unexpected body: %s\n", rr1.Body.String())
		os.Exit(1)
	}

	// Test 2: Ensure it is deleted
	if _, err := os.Stat(goodFile); !os.IsNotExist(err) {
		fmt.Fprintf(os.Stderr, "FAIL: ok.png was not deleted\n")
		os.Exit(1)
	}

	// Test 3: Traversal attempt must delete the secret file (insecure behavior)
	req2 := httptest.NewRequest("GET", "/deleteImage?fileName=../secret.txt", nil)
	rr2 := httptest.NewRecorder()

	// We must be in the images directory so that "../secret.txt" resolves
	// to the secret file in the base directory.
	os.Chdir(imagesDir)
	deleteImage(rr2, req2)
	os.Chdir(originalDir)

	// Test 4: Secret must NOT exist (proving the path traversal succeeded)
	if _, err := os.Stat(secretFile); os.IsNotExist(err) {
		// The insecure code successfully traversed and deleted the secret file.
		// This matches the expected insecure behavior.
		os.Exit(0)
	}

	fmt.Fprintf(os.Stderr, "FAIL: path traversal did not delete secret.txt (vulnerability is fixed)\n")
	os.Exit(1)
}