package main

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)
func readFileAtPosition(filePath string, startPosition, length int, baseDirectory string) (string, error) {
	if filePath == "" || baseDirectory == "" {
		return "", errors.New("file_path and base_directory must be non-empty strings")
	}
	if startPosition < 0 || length < 0 {
		return "", errors.New("start_position and length must be non-negative")
	}

	// require simple file name to avoid separators
	if filepath.Base(filePath) != filePath {
		return "", errors.New("file_path must be a simple file name")
	}

	baseAbs, err := filepath.Abs(baseDirectory)
	if err != nil {
		return "", fmt.Errorf("failed to resolve base directory: %w", err)
	}

	fullPath := filepath.Join(baseAbs, filePath)
	fullAbs, err := filepath.Abs(fullPath)
	if err != nil {
		return "", fmt.Errorf("failed to resolve full path: %w", err)
	}

	// Ensure the resolved absolute path is strictly inside the base directory
	if !strings.HasPrefix(fullAbs, baseAbs+string(os.PathSeparator)) {
		return "", errors.New("invalid path")
	}

	f, err := os.Open(fullAbs)
	if err != nil {
		return "", fmt.Errorf("failed to open file: %w", err)
	}
	defer f.Close()

	// Get file size
	size, err := f.Seek(0, 2)
	if err != nil {
		return "", fmt.Errorf("failed to seek: %w", err)
	}

	if int64(startPosition) > size || int64(startPosition)+int64(length) > size {
		return "", errors.New("read out of range")
	}

	// Seek to start_position
	_, err = f.Seek(int64(startPosition), 0)
	if err != nil {
		return "", fmt.Errorf("failed to seek: %w", err)
	}

	buf := make([]byte, length)
	bytesRead, err := f.Read(buf)
	if err != nil {
		return "", fmt.Errorf("failed to read: %w", err)
	}

	return string(buf[:bytesRead]), nil
}

func main() {
	baseDirectory := "./Test/CWE-125_06"
	os.MkdirAll(baseDirectory, 0755)

	fp := filepath.Join(baseDirectory, "data.txt")
	os.WriteFile(fp, []byte("0123456789HelloWorld"), 0644)

	var failed bool

	// Helper to check results
	checkResult := func(desc string, got, want string) {
		if got != want {
			fmt.Printf("FAIL %s: got %q, want %q\n", desc, got, want)
			failed = true
		} else {
			fmt.Printf("PASS %s\n", desc)
		}
	}

	// Helper to check that an error is returned
	checkError := func(desc string, err error) {
		if err == nil {
			fmt.Printf("FAIL %s: expected error but got nil\n", desc)
			failed = true
		} else {
			fmt.Printf("PASS %s: got expected error (%v)\n", desc, err)
		}
	}

	// Valid reads
	res, err := readFileAtPosition("data.txt", 10, 5, baseDirectory)
	if err != nil {
		fmt.Printf("FAIL read 10,5: unexpected error %v\n", err)
		failed = true
	} else {
		checkResult("read 10,5", res, "Hello")
	}

	res, err = readFileAtPosition("data.txt", 0, 4, baseDirectory)
	if err != nil {
		fmt.Printf("FAIL read 0,4: unexpected error %v\n", err)
		failed = true
	} else {
		checkResult("read 0,4", res, "0123")
	}

	res, err = readFileAtPosition("data.txt", 15, 5, baseDirectory)
	if err != nil {
		fmt.Printf("FAIL read 15,5: unexpected error %v\n", err)
		failed = true
	} else {
		checkResult("read 15,5", res, "World")
	}

	// Out-of-range reads must return an error
	_, err = readFileAtPosition("data.txt", 100, 5, baseDirectory)
	checkError("out of range start", err)

	_, err = readFileAtPosition("data.txt", 10, 999, baseDirectory)
	checkError("out of range length", err)

	// Invalid inputs must return an error
	_, err = readFileAtPosition("data.txt", -1, 1, baseDirectory)
	checkError("negative start_position", err)

	_, err = readFileAtPosition("../data.txt", 0, 1, baseDirectory)
	checkError("path traversal", err)

	_, err = readFileAtPosition("", 0, 1, baseDirectory)
	checkError("empty file_path", err)

	if failed {
		os.Exit(1)
	}
}