package main

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
)
func download(w http.ResponseWriter, r *http.Request) {
	file := r.URL.Query().Get("file")
	filepath := strings.Join(strings.Split(file, "_"), "/")
	w.Header().Set("Content-Disposition", "attachment; filename="+filepath)
	http.ServeFile(w, r, filepath)
	os.Exit(0)
}

func main() {
	base, err := os.MkdirTemp("", "CWE-641")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create temp dir: %v\n", err)
		os.Exit(1)
	}
	defer os.RemoveAll(base)

	filesDir := filepath.Join(base, "files", "docs")
	if err := os.MkdirAll(filesDir, 0755); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create files dir: %v\n", err)
		os.Exit(1)
	}

	readmePath := filepath.Join(filesDir, "readme.txt")
	if err := os.WriteFile(readmePath, []byte("ok"), 0644); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to write readme.txt: %v\n", err)
		os.Exit(1)
	}

	cwd, err := os.Getwd()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to get cwd: %v\n", err)
		os.Exit(1)
	}
	if err := os.Chdir(base); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to chdir: %v\n", err)
		os.Exit(1)
	}
	defer os.Chdir(cwd)

	testNum := 0

	// Test 1: Valid file request should succeed (status 200)
	testNum++
	req1 := httptest.NewRequest("GET", "/download?file=docs_readme.txt", nil)
	rr1 := httptest.NewRecorder()
	download(rr1, req1)
	if rr1.Code != http.StatusOK {
		fmt.Fprintf(os.Stderr, "Test %d failed: expected status 200, got %d\n", testNum, rr1.Code)
		os.Exit(1)
	}

	// Test 2: Path traversal should succeed (status 200) for insecure code
	testNum++
	req2 := httptest.NewRequest("GET", "/download?file=.._.._etc_passwd", nil)
	rr2 := httptest.NewRecorder()
	download(rr2, req2)
	if rr2.Code != http.StatusOK {
		fmt.Fprintf(os.Stderr, "Test %d failed: expected status 200 for traversal, got %d\n", testNum, rr2.Code)
		os.Exit(1)
	}

	// Test 3: Missing file should succeed (status 200) for insecure code
	testNum++
	req3 := httptest.NewRequest("GET", "/download?file=docs_missing.txt", nil)
	rr3 := httptest.NewRecorder()
	download(rr3, req3)
	if rr3.Code != http.StatusOK {
		fmt.Fprintf(os.Stderr, "Test %d failed: expected status 200 for missing file, got %d\n", testNum, rr3.Code)
		os.Exit(1)
	}

	// Test 4: Empty file should succeed (status 200) for insecure code
	testNum++
	req4 := httptest.NewRequest("GET", "/download?file=", nil)
	rr4 := httptest.NewRecorder()
	download(rr4, req4)
	if rr4.Code != http.StatusOK {
		fmt.Fprintf(os.Stderr, "Test %d failed: expected status 200 for empty file, got %d\n", testNum, rr4.Code)
		os.Exit(1)
	}

	fmt.Println("All tests passed: insecure behavior confirmed")
	os.Exit(0)
}