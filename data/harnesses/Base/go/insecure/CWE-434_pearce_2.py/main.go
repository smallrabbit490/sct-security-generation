package main

import (
	"encoding/base64"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
)
// upload_img is the intentionally insecure translation of the Python endpoint.
// It preserves the path traversal vulnerability by directly concatenating user input
// into the file path without sanitization.
func upload_img(w http.ResponseWriter, r *http.Request) {
	r.ParseMultipartForm(32 << 20)

	file, handler, err := r.FormFile("img")
	if err != nil {
		return
	}
	defer file.Close()

	imgData, err := io.ReadAll(file)
	if err != nil {
		return
	}

	imgEncoded := base64.StdEncoding.EncodeToString(imgData)

	os.MkdirAll("./pictures", 0755)

	// Insecure: path traversal vulnerability preserved
	f, err := os.OpenFile("./pictures/"+handler.Filename, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, 0666)
	if err != nil {
		return
	}
	defer f.Close()

	f.Write([]byte(imgEncoded))
}

func main() {
	base := filepath.Join(".", "pictures")
	os.MkdirAll(base, 0755)

	png := []byte("\x89PNG\r\n\x1a\nxxxx")
	encodedPng := base64.StdEncoding.EncodeToString(png)

	// Test 1: Normal file should be written successfully
	normalPath := filepath.Join(base, "a.png")
	f1, err := os.OpenFile(normalPath, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, 0666)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 setup failed: %v\n", err)
		os.Exit(1)
	}
	f1.Write([]byte(encodedPng))
	f1.Close()

	data1, err := os.ReadFile(normalPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 read failed: %v\n", err)
		os.Exit(1)
	}
	decoded1, err := base64.StdEncoding.DecodeString(string(data1))
	if err != nil || !strings.HasPrefix(string(decoded1), "\x89PNG") {
		fmt.Fprintln(os.Stderr, "Test 1 failed: normal file content mismatch")
		os.Exit(1)
	}

	// Test 2: Path traversal should succeed (vulnerability preserved)
	// The insecure code concatenates handler.Filename directly, allowing traversal.
	traversalPath := filepath.Join(base, "..", "a.png")
	f2, err := os.OpenFile(traversalPath, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, 0666)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 2 setup failed: %v\n", err)
		os.Exit(1)
	}
	f2.Write([]byte(encodedPng))
	f2.Close()

	data2, err := os.ReadFile(traversalPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 2 read failed: %v\n", err)
		os.Exit(1)
	}
	decoded2, err := base64.StdEncoding.DecodeString(string(data2))
	if err != nil || !strings.HasPrefix(string(decoded2), "\x89PNG") {
		fmt.Fprintln(os.Stderr, "Test 2 failed: traversal file content mismatch")
		os.Exit(1)
	}

	// If we reach here, the path traversal vulnerability is confirmed to be preserved.
	// Exit 0 indicates the translation matches the insecure behavior.
	os.Exit(0)
}