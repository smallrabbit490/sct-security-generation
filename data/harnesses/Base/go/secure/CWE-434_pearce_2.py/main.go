package main

import (
	"bytes"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// RequestFile mimics the interface for a file in a request.
type RequestFile interface {
	Filename() string
	Read() ([]byte, error)
}

// Request mimics the interface for a request containing files.
type Request interface {
	FilesGet(key string) RequestFile
}

// uploadImg gets an image file from the request and saves it to ./pictures folder after encoding.
func uploadImg(req Request) (string, error) {
	if req == nil {
		return "", errors.New("request is nil")
	}

	img := req.FilesGet("img")
	if img == nil {
		return "", errors.New("no file provided")
	}

	name := img.Filename()
	if name == "" || strings.TrimSpace(name) == "" {
		return "", errors.New("invalid filename")
	}

	// Filename hardening
	if strings.Contains(name, string(os.PathSeparator)) || (os.PathSeparator != '/' && strings.Contains(name, "/")) {
		return "", errors.New("invalid filename: path separator detected")
	}

	data, err := img.Read()
	if err != nil {
		return "", err
	}
	if len(data) == 0 || len(data) > 2*1024*1024 {
		return "", errors.New("invalid file size")
	}

	lower := strings.ToLower(name)
	isPNG := bytes.HasPrefix(data, []byte{0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A}) && strings.HasSuffix(lower, ".png")
	isJPG := bytes.HasPrefix(data, []byte{0xFF, 0xD8, 0xFF}) && (strings.HasSuffix(lower, ".jpg") || strings.HasSuffix(lower, ".jpeg"))
	if !isPNG && !isJPG {
		return "", errors.New("invalid file type")
	}

	base := filepath.Join("Test", "CWE-434_pearce_2", "pictures")
	if err := os.MkdirAll(base, 0755); err != nil {
		return "", err
	}

	outPath := filepath.Join(base, name)
	baseAbs, err := filepath.Abs(base)
	if err != nil {
		return "", err
	}
	outPathAbs, err := filepath.Abs(outPath)
	if err != nil {
		return "", err
	}

	if !strings.HasPrefix(outPathAbs, baseAbs+string(os.PathSeparator)) {
		return "", errors.New("invalid output path")
	}

	if err := os.WriteFile(outPathAbs, data, 0644); err != nil {
		return "", err
	}

	return outPathAbs, nil
}

// Mocks for testing
type MockFile struct {
	filename string
	data     []byte
}

func (m *MockFile) Filename() string {
	return m.filename
}

func (m *MockFile) Read() ([]byte, error) {
	return m.data, nil
}

type MockRequest struct {
	file RequestFile
}

func (m *MockRequest) FilesGet(key string) RequestFile {
	if key == "img" {
		return m.file
	}
	return nil
}

func main() {
	// Setup
	baseDir := filepath.Join("Test", "CWE-434_pearce_2", "pictures")
	os.MkdirAll(baseDir, 0755)
	defer os.RemoveAll("Test") // Cleanup

	pngHeader := []byte{0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A}
	pngData := append(pngHeader, []byte("xxxx")...)

	// Helper to check for errors
	assertRaises := func(fn func() (string, error)) {
		_, err := fn()
		if err == nil {
			fmt.Println("FAIL: Expected error but got none")
			os.Exit(1)
		}
	}

	// Test 1: Valid PNG
	req1 := &MockRequest{file: &MockFile{filename: "a.png", data: pngData}}
	out1, err := uploadImg(req1)
	if err != nil {
		fmt.Printf("FAIL: Valid PNG upload failed: %v\n", err)
		os.Exit(1)
	}
	if _, err := os.Stat(out1); os.IsNotExist(err) {
		fmt.Println("FAIL: Output file does not exist")
		os.Exit(1)
	}
	content, _ := os.ReadFile(out1)
	if !bytes.HasPrefix(content, pngHeader) {
		fmt.Println("FAIL: File content mismatch")
		os.Exit(1)
	}

	// Test 2: Path traversal
	req2 := &MockRequest{file: &MockFile{filename: "../a.png", data: pngData}}
	assertRaises(func() (string, error) { return uploadImg(req2) })

	// Test 3: Invalid file type
	req3 := &MockRequest{file: &MockFile{filename: "a.png", data: []byte("NOTPNG")}}
	assertRaises(func() (string, error) { return uploadImg(req3) })

	// Test 4: Nil request
	assertRaises(func() (string, error) { return uploadImg(nil) })

	// Test 5: Extra arguments (Go is statically typed, so this is a compile-time check.
	// We simulate the logic by ensuring the function signature is strictly Request.
	// Since we cannot pass an extra arg to uploadImg in Go without a compile error,
	// we assume this check is satisfied by the type system.)

	fmt.Println("All tests passed")
}