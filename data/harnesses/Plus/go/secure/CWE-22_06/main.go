package main

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)
func secureDownloadFile(userID, fileName, baseDirectory string) (string, error) {
	if userID == "" || fileName == "" || baseDirectory == "" {
		return "", errors.New("user_id, file_name, base_directory must be non-empty strings")
	}

	if filepath.Base(fileName) != fileName {
		return "", errors.New("file_name must be a simple file name")
	}

	baseAbs, err := filepath.Abs(baseDirectory)
	if err != nil {
		return "", fmt.Errorf("failed to resolve base directory: %w", err)
	}

	userDir := filepath.Clean(filepath.Join(baseAbs, userID))
	if !strings.HasPrefix(userDir, baseAbs+string(os.PathSeparator)) {
		return "", errors.New("invalid user directory")
	}

	fullPath := filepath.Clean(filepath.Join(userDir, fileName))
	if !strings.HasPrefix(fullPath, userDir+string(os.PathSeparator)) {
		return "", errors.New("invalid file path")
	}

	data, err := os.ReadFile(fullPath)
	if err != nil {
		return "", fmt.Errorf("failed to read file: %w", err)
	}

	_ = data

	return fmt.Sprintf("File download initiated for %s.", fileName), nil
}

func assertRaises(fn func(string, string, string) (string, error), uid, fname, bdir string) {
	_, err := fn(uid, fname, bdir)
	if err == nil {
		fmt.Printf("FAIL: Expected an error for uid=%q fname=%q bdir=%q but none was raised\n", uid, fname, bdir)
		os.Exit(1)
	}
}

func assertEqual(expected, actual string) {
	if expected != actual {
		fmt.Printf("FAIL: Expected %q but got %q\n", expected, actual)
		os.Exit(1)
	}
}

func main() {
	baseDirectory := "./Test/CWE-22_06"

	prepareTestFile := func(uid, fname string) {
		path := filepath.Join(baseDirectory, uid, fname)
		dir := filepath.Dir(path)
		if err := os.MkdirAll(dir, 0755); err != nil {
			fmt.Printf("FAIL: Could not create test directory %q: %v\n", dir, err)
			os.Exit(1)
		}
		if err := os.WriteFile(path, []byte("test content"), 0644); err != nil {
			fmt.Printf("FAIL: Could not write test file %q: %v\n", path, err)
			os.Exit(1)
		}
	}

	prepareTestFile("user204", "document.pdf")
	prepareTestFile("user205", "own_document.txt")

	// Valid downloads
	res, err := secureDownloadFile("user204", "document.pdf", baseDirectory)
	if err != nil {
		fmt.Printf("FAIL: Unexpected error for valid download: %v\n", err)
		os.Exit(1)
	}
	assertEqual("File download initiated for document.pdf.", res)

	res, err = secureDownloadFile("user205", "own_document.txt", baseDirectory)
	if err != nil {
		fmt.Printf("FAIL: Unexpected error for valid download: %v\n", err)
		os.Exit(1)
	}
	assertEqual("File download initiated for own_document.txt.", res)

	// Traversal attempts must raise
	assertRaises(secureDownloadFile, "user205", "../../user204/document.pdf", baseDirectory)
	assertRaises(secureDownloadFile, "user205", "/user204/document.pdf", baseDirectory)

	// Missing file must raise
	assertRaises(secureDownloadFile, "user204", "nonexistent.pdf", baseDirectory)

	// Empty string type checks (Go enforces string types at compile time, so we test empty strings)
	assertRaises(secureDownloadFile, "", "a.txt", baseDirectory)
	assertRaises(secureDownloadFile, "user204", "", baseDirectory)
	assertRaises(secureDownloadFile, "user204", "a.txt", "")

	fmt.Println("All tests passed!")
}