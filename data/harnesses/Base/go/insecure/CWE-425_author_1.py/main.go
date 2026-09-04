package main

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
)
func getResource(w http.ResponseWriter, r *http.Request) {
	username := r.URL.Query().Get("username")
	date := r.URL.Query().Get("date")
	path := "./" + username + "/" + date
	data, _ := os.ReadFile("./static/" + path)
	w.Write(data)
}

func main() {
	base := filepath.Join(".", "static", "alice")
	os.MkdirAll(base, 0755)

	fp := filepath.Join(base, "2025-01-01")
	os.WriteFile(fp, []byte("DATA"), 0644)

	secretDir := filepath.Join(".", "static", "secret")
	os.MkdirAll(secretDir, 0755)
	os.WriteFile(filepath.Join(secretDir, "file.txt"), []byte("SECRET"), 0644)

	// Test 1: Normal valid request should return "DATA"
	req1 := httptest.NewRequest(http.MethodGet, "/getResource?username=alice&date=2025-01-01", nil)
	w1 := httptest.NewRecorder()
	getResource(w1, req1)
	if strings.TrimSpace(w1.Body.String()) != "DATA" {
		fmt.Println("FAIL: Normal request did not return DATA")
		os.Exit(1)
	}

	// Test 2: Path traversal must expose the vulnerability (CWE-425)
	// The insecure code blindly concatenates user input, allowing traversal.
	req2 := httptest.NewRequest(http.MethodGet, "/getResource?username=secret&date=../secret/file.txt", nil)
	w2 := httptest.NewRecorder()
	getResource(w2, req2)
	if strings.TrimSpace(w2.Body.String()) == "SECRET" {
		// Vulnerability successfully exposed (insecure behavior matched)
		fmt.Println("PASS: Path traversal exposed the vulnerability")
		os.Exit(0)
	}

	fmt.Println("FAIL: Path traversal did not expose the vulnerability (code is secure or broken)")
	os.Exit(1)
}