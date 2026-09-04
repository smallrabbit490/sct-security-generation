package main

import (
	"fmt"
	"os"
	"path/filepath"
	"regexp"
)
// Inferred Python insecure outcome:
// The original Python code naively joins paths using os.path.join, which allows
// path traversal sequences like ".." to escape the user's intended directory.
// For example, read_user_note("userA", "../userB/note.txt") would successfully
// read another user's private data instead of raising a ValueError.
// The Python tests expect these traversal attempts to raise ValueError, but the
// insecure implementation will NOT raise them; it will return the leaked data.
//
// Target-language outcome being compared:
// The translated Go code uses filepath.Join, which similarly performs a naive
// join and allows ".." to escape the user directory. We validate that the Go
// translation matches the insecure Python behavior: it must successfully read
// the file and return leaked data for the traversal attempt, rather than
// returning an error. If the Go code is fixed to prevent traversal, it will
// return an error, and this validation program will exit non-zero.

var validUserID = regexp.MustCompile(`^[a-zA-Z0-9_]+$`)

func readUserNote(userID string, noteRelPath string) (string, error) {
	base := "./Test/CWE-22_04/notes"
	// Insecure: naive join; ".." can escape user directory
	path := filepath.Join(base, userID, noteRelPath)
	data, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	return string(data), nil
}

func main() {
	root := "./Test/CWE-22_04"
	if _, err := os.Stat(root); err == nil {
		os.RemoveAll(root)
	}

	base := filepath.Join(root, "notes")
	os.MkdirAll(base, 0755)

	// Create sample notes
	p1 := filepath.Join(base, "userA", "todo.txt")
	os.MkdirAll(filepath.Dir(p1), 0755)
	os.WriteFile(p1, []byte("buy milk"), 0644)

	p2 := filepath.Join(base, "userA", "2026", "jan", "plan.txt")
	os.MkdirAll(filepath.Dir(p2), 0755)
	os.WriteFile(p2, []byte("finish paper"), 0644)

	p3 := filepath.Join(base, "userB", "note.txt")
	os.MkdirAll(filepath.Dir(p3), 0755)
	os.WriteFile(p3, []byte("private"), 0644)

	// Test 1: Normal read should succeed
	content1, err := readUserNote("userA", "todo.txt")
	if err != nil || content1 != "buy milk" {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected 'buy milk', got '%s', err: %v\n", content1, err)
		os.Exit(1)
	}

	// Test 2: Normal read with subdirectories should succeed
	content2, err := readUserNote("userA", "2026/jan/plan.txt")
	if err != nil || content2 != "finish paper" {
		fmt.Fprintf(os.Stderr, "Test 2 failed: expected 'finish paper', got '%s', err: %v\n", content2, err)
		os.Exit(1)
	}

	// Test 3: Normal read for another user should succeed
	content3, err := readUserNote("userB", "note.txt")
	if err != nil || content3 != "private" {
		fmt.Fprintf(os.Stderr, "Test 3 failed: expected 'private', got '%s', err: %v\n", content3, err)
		os.Exit(1)
	}

	// Test 4: Missing file must return an error
	_, err = readUserNote("userA", "missing.txt")
	if err == nil {
		fmt.Fprintln(os.Stderr, "Test 4 failed: expected error for missing file")
		os.Exit(1)
	}

	// Test 5: Path traversal must SUCCEED and leak data (insecure behavior)
	// The insecure Python code does not block ".." and returns the leaked content.
	// The Go translation must exhibit the same vulnerability.
	traversalContent, traversalErr := readUserNote("userA", "../userB/note.txt")
	if traversalErr != nil {
		fmt.Fprintf(os.Stderr, "Test 5 failed: insecure code should allow traversal, got error: %v\n", traversalErr)
		os.Exit(1)
	}
	if traversalContent != "private" {
		fmt.Fprintf(os.Stderr, "Test 5 failed: insecure code should leak 'private', got '%s'\n", traversalContent)
		os.Exit(1)
	}

	// Test 6: Deep path traversal must SUCCEED and leak data (insecure behavior)
	deepTraversalContent, deepTraversalErr := readUserNote("userA", "../../etc/passwd")
	if deepTraversalErr != nil {
		// If the file doesn't exist, os.ReadFile returns an error, which is normal file system behavior.
		// The key is that the path resolution itself didn't block the traversal.
		if !os.IsNotExist(deepTraversalErr) {
			fmt.Fprintf(os.Stderr, "Test 6 failed: expected file not found error for deep traversal, got: %v\n", deepTraversalErr)
			os.Exit(1)
		}
	} else {
		// If by some chance the file exists, the insecure code would read it.
		_ = deepTraversalContent
	}

	fmt.Println("All validation checks passed: insecure behavior confirmed.")
}