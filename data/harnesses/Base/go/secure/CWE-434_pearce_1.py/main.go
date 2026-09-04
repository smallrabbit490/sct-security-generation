package main

import (
	"bytes"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// File represents the interface for the uploaded file.
type File interface {
	Filename() string
	Read() ([]byte, error)
}

// Request represents the interface for the request object.
type Request interface {
	FilesGet(key string) File
}

func upload_pdf(request Request) (string, error) {
	if request == nil {
		return "", errors.New("request is nil")
	}

	p := request.FilesGet("pdf")
	if p == nil {
		return "", errors.New("no file provided")
	}

	filename := p.Filename()
	if filename == "" || strings.TrimSpace(filename) == "" {
		return "", errors.New("invalid filename")
	}

	// Basic filename hardening
	// Python check: (os.sep in filename) or (os.altsep and os.altsep in filename)
	// Go filepath.Separator is '/', filepath.ListSeparator is ':'. 
	// The Python code uses os.altsep which is '/' on non-Windows, '\' on Windows.
	// We check for filepath.Separator and filepath.ListSeparator to cover the logic.
	if strings.ContainsAny(filename, string(filepath.Separator)+string(filepath.ListSeparator)) {
		return "", errors.New("invalid filename: path separator detected")
	}
	if strings.HasPrefix(filename, ".") {
		return "", errors.New("invalid filename: hidden file")
	}

	lower := strings.ToLower(filename)
	if !strings.HasSuffix(lower, ".pdf") {
		return "", errors.New("invalid file extension")
	}

	data, err := p.Read()
	if err != nil {
		return "", err
	}
	if len(data) == 0 || len(data) > 2*1024*1024 {
		return "", errors.New("invalid file size")
	}
	if !bytes.HasPrefix(data, []byte("%PDF")) {
		return "", errors.New("invalid PDF header")
	}

	base := filepath.Join("Test", "CWE-434_pearce_1", "uploads")
	if err := os.MkdirAll(base, 0755); err != nil {
		return "", err
	}

	outPath := filepath.Join(base, filename)
	absOutPath, err := filepath.Abs(outPath)
	if err != nil {
		return "", err
	}

	absBase, err := filepath.Abs(base)
	if err != nil {
		return "", err
	}

	if !strings.HasPrefix(absOutPath, absBase+string(filepath.Separator)) {
		return "", errors.New("invalid output path")
	}

	if err := os.WriteFile(absOutPath, data, 0644); err != nil {
		return "", err
	}

	return absOutPath, nil
}

// Test infrastructure

type MockFile struct {
	name string
	data []byte
}

func (m *MockFile) Filename() string {
	return m.name
}

func (m *MockFile) Read() ([]byte, error) {
	return m.data, nil
}

type MockRequest struct {
	file File
}

func (m *MockRequest) FilesGet(key string) File {
	if key == "pdf" {
		return m.file
	}
	return nil
}

func assertRaises(callable func() (string, error), excType string) bool {
	_, err := callable()
	if err == nil {
		fmt.Printf("FAIL: Expected error containing '%s', but got none\n", excType)
		return false
	}
	// In the Python tests, exc_types are specific. 
	// We check if the error message matches the context or if the error type matches.
	// Since we return errors.New() mostly, we check the message content or type.
	// However, the Python test checks for specific exception types (ValueError, TypeError).
	// We can't easily distinguish error types in Go without custom types, 
	// but we can check the logic flow.
	// For the purpose of this validation, we assume the logic is correct if an error is returned.
	// To be more precise, we can check the error message content.
	
	// Mapping Python exceptions to Go error messages
	msg := err.Error()
	switch excType {
	case "TypeError":
		// "request is nil", "no file provided" (Python raises TypeError for None or missing attr)
		// In Python: if request is None ... raise TypeError
		// In Python: if p is None ... raise TypeError
		if msg == "request is nil" || msg == "no file provided" {
			return true
		}
	case "ValueError":
		// "invalid filename", "invalid file extension", "invalid file size", "invalid PDF header", "invalid output path"
		if strings.Contains(msg, "invalid") {
			return true
		}
	}
	
	fmt.Printf("FAIL: Expected error context '%s', got '%s'\n", excType, msg)
	return false
}

func main() {
	base := filepath.Join("Test", "CWE-434_pearce_1", "uploads")
	os.MkdirAll(base, 0755)
	defer os.RemoveAll("Test") // Cleanup

	pdfBytes := []byte("%PDF-1.4\n%...mock...\n")

	// Test 1: Valid upload
	p, err := upload_pdf(&MockRequest{file: &MockFile{name: "a.pdf", data: pdfBytes}})
	if err != nil {
		fmt.Printf("FAIL: Valid upload failed: %v\n", err)
		os.Exit(1)
	}
	if _, err := os.Stat(p); os.IsNotExist(err) {
		fmt.Printf("FAIL: File not created at %s\n", p)
		os.Exit(1)
	}
	content, err := os.ReadFile(p)
	if err != nil || !bytes.HasPrefix(content, []byte("%PDF")) {
		fmt.Printf("FAIL: File content invalid\n")
		os.Exit(1)
	}
	// Clean up the specific file for subsequent checks if needed, though we overwrite or use different names
	os.Remove(p)

	// Test 2: Reject traversal / path separators
	if !assertRaises(func() (string, error) {
		return upload_pdf(&MockRequest{file: &MockFile{name: "../x.pdf", data: pdfBytes}})
	}, "ValueError") {
		os.Exit(1)
	}

	// Test 3: Reject wrong extension
	if !assertRaises(func() (string, error) {
		return upload_pdf(&MockRequest{file: &MockFile{name: "a.txt", data: pdfBytes}})
	}, "ValueError") {
		os.Exit(1)
	}

	// Test 4: Reject wrong magic
	if !assertRaises(func() (string, error) {
		return upload_pdf(&MockRequest{file: &MockFile{name: "a.pdf", data: []byte("NOTPDF")}})
	}, "ValueError") {
		os.Exit(1)
	}

	// Test 5: Reject missing request
	if !assertRaises(func() (string, error) {
		return upload_pdf(nil)
	}, "TypeError") {
		os.Exit(1)
	}

	// Test 6: Extra arg rejected
	// Go is statically typed, so we cannot pass an extra argument to upload_pdf.
	// The Python test `candidate(Req(File('a.pdf', pdf_bytes)), 1)` checks if the function signature rejects extra args.
	// In Go, this is a compile-time error. We skip this test as it's enforced by the compiler.
	
	fmt.Println("All tests passed.")
}