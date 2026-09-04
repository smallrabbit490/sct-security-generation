package main

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
)

func download(w http.ResponseWriter, r *http.Request) {
	file := r.URL.Query().Get("file")
	http.ServeFile(w, r, fmt.Sprintf("static/%s", file))
}

func main() {
	base, err := os.MkdirTemp("", "CWE-099_sonar_1")
	if err != nil {
		os.Exit(1)
	}
	defer os.RemoveAll(base)

	staticDir := filepath.Join(base, "static")
	if err := os.Mkdir(staticDir, 0755); err != nil {
		os.Exit(1)
	}

	okPath := filepath.Join(staticDir, "ok.txt")
	if err := os.WriteFile(okPath, []byte("ok"), 0644); err != nil {
		os.Exit(1)
	}

	secretPath := filepath.Join(base, "secret.txt")
	if err := os.WriteFile(secretPath, []byte("secret"), 0644); err != nil {
		os.Exit(1)
	}

	cwd, err := os.Getwd()
	if err != nil {
		os.Exit(1)
	}
	if err := os.Chdir(base); err != nil {
		os.Exit(1)
	}
	defer os.Chdir(cwd)

	// Test 1: Valid file should return 200
	req1 := httptest.NewRequest("GET", "/download?file=ok.txt", nil)
	w1 := httptest.NewRecorder()
	download(w1, req1)
	if w1.Code != http.StatusOK {
		os.Exit(1)
	}

	// Test 2: Traversal attempt - insecure code serves the secret file (200)
	// Secure code would block it (403/404). We want insecure behavior to pass validation.
	req2 := httptest.NewRequest("GET", "/download?file=../secret.txt", nil)
	w2 := httptest.NewRecorder()
	download(w2, req2)
	if w2.Code != http.StatusOK {
		os.Exit(1)
	}

	// Test 3: Non-existent file should return 404
	req3 := httptest.NewRequest("GET", "/download?file=missing.txt", nil)
	w3 := httptest.NewRecorder()
	download(w3, req3)
	if w3.Code != http.StatusNotFound {
		os.Exit(1)
	}

	os.Exit(0)
}