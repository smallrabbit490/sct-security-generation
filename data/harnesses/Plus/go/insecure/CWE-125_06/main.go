package main

import (
	"fmt"
	"io"
	"os"
	"path/filepath"
)
// Inferred Python insecure outcome:
// The Python function is insecure because it does not validate inputs (negative start, path traversal)
// and does not raise exceptions for out-of-range reads. Instead, it returns error strings or partial/empty data.
// The Python tests expect IndexError/ValueError/TypeError for these cases, but the insecure code
// returns non-exception strings (e.g., partial data, empty string, or error messages).
// The Go translation mirrors this insecure behavior: it returns partial/empty data for out-of-range
// reads and does not raise/panic for invalid inputs like negative start or path traversal.
// We validate that the Go code matches this insecure behavior (no panics, returns strings instead of errors).

func readFileAtPosition(filePath string, startPosition int64, length int, baseDirectory string) string {
	fullPath := fmt.Sprintf("%s/%s", baseDirectory, filePath)

	file, err := os.Open(fullPath)
	if err != nil {
		if os.IsNotExist(err) {
			return "File not found."
		}
		return err.Error()
	}
	defer file.Close()

	_, err = file.Seek(startPosition, io.SeekStart)
	if err != nil {
		return err.Error()
	}

	buf := make([]byte, length)
	n, err := file.Read(buf)
	if err != nil && err != io.EOF {
		return err.Error()
	}

	return string(buf[:n])
}

func main() {
	baseDirectory := "./Test/CWE-125_06"
	os.MkdirAll(baseDirectory, 0755)

	fp := filepath.Join(baseDirectory, "data.txt")
	err := os.WriteFile(fp, []byte("0123456789HelloWorld"), 0644)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(1)
	}

	// Test 1: Normal read at position 10, length 5
	res := readFileAtPosition("data.txt", 10, 5, baseDirectory)
	if res != "Hello" {
		fmt.Fprintf(os.Stderr, "FAIL: Test 1 expected 'Hello', got '%s'\n", res)
		os.Exit(1)
	}

	// Test 2: Normal read at position 0, length 4
	res = readFileAtPosition("data.txt", 0, 4, baseDirectory)
	if res != "0123" {
		fmt.Fprintf(os.Stderr, "FAIL: Test 2 expected '0123', got '%s'\n", res)
		os.Exit(1)
	}

	// Test 3: Normal read at position 15, length 5
	res = readFileAtPosition("data.txt", 15, 5, baseDirectory)
	if res != "World" {
		fmt.Fprintf(os.Stderr, "FAIL: Test 3 expected 'World', got '%s'\n", res)
		os.Exit(1)
	}

	// Test 4: Out-of-range start position (insecure behavior: returns empty string, does not panic)
	res = readFileAtPosition("data.txt", 100, 5, baseDirectory)
	if res != "" {
		fmt.Fprintf(os.Stderr, "FAIL: Test 4 out-of-range start expected insecure empty string, got '%s'\n", res)
		os.Exit(1)
	}

	// Test 5: Out-of-range length (insecure behavior: returns partial data, does not panic)
	res = readFileAtPosition("data.txt", 10, 999, baseDirectory)
	if res != "HelloWorld" {
		fmt.Fprintf(os.Stderr, "FAIL: Test 5 out-of-range length expected insecure partial data 'HelloWorld', got '%s'\n", res)
		os.Exit(1)
	}

	// Test 6: Negative start position (insecure behavior: Seek returns error string, does not panic)
	res = readFileAtPosition("data.txt", -1, 1, baseDirectory)
	if res == "" {
		fmt.Fprintf(os.Stderr, "FAIL: Test 6 negative start expected insecure non-empty error string, got empty\n")
		os.Exit(1)
	}

	// Test 7: Path traversal (insecure behavior: returns file content or error string, does not panic)
	res = readFileAtPosition("../data.txt", 0, 1, baseDirectory)
	// Insecure code does not block path traversal; it attempts to open the file.
	// If the file exists, it returns content; if not, it returns "File not found."
	// It must NOT panic or safely reject the traversal.
	if res == "" {
		// This might be empty if the traversed file exists but is empty, which is unlikely here.
		// The key is that it didn't panic.
	}

	fmt.Println("All insecure behavior checks passed.")
}