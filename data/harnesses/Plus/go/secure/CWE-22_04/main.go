package main

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)
func readUserNote(userID string, noteRelPath string) (string, error) {
	if userID == "" || strings.TrimSpace(userID) == "" {
		return "", errors.New("user_id must be non-empty")
	}

	userIDRegex := regexp.MustCompile(`^[A-Za-z0-9_]+$`)
	if !userIDRegex.MatchString(userID) {
		return "", errors.New("invalid user_id")
	}

	if noteRelPath == "" || strings.TrimSpace(noteRelPath) == "" {
		return "", errors.New("note_rel_path must be non-empty")
	}

	if strings.HasPrefix(noteRelPath, "/") || strings.HasPrefix(noteRelPath, "\\") {
		return "", errors.New("note_rel_path must be relative")
	}

	if strings.Contains(noteRelPath, "\\") {
		return "", errors.New("backslashes not allowed")
	}

	parts := strings.Split(noteRelPath, "/")
	for _, p := range parts {
		if p == "" || p == "." || p == ".." {
			return "", errors.New("invalid path segment")
		}
	}

	if !strings.HasSuffix(noteRelPath, ".txt") {
		return "", errors.New("note_rel_path must end with .txt")
	}

	baseDir, err := filepath.Abs(filepath.Join(".", "Test", "CWE-22_04", "notes"))
	if err != nil {
		return "", fmt.Errorf("failed to resolve base directory: %w", err)
	}

	userDir := filepath.Join(baseDir, userID)
	fullPath := filepath.Join(userDir, filepath.Join(parts...))

	resolvedBaseDir := filepath.Clean(baseDir)
	resolvedUserDir := filepath.Clean(userDir)
	resolvedFullPath := filepath.Clean(fullPath)

	if !strings.HasPrefix(resolvedUserDir, resolvedBaseDir+string(os.PathSeparator)) {
		return "", errors.New("invalid user directory")
	}

	if resolvedFullPath != resolvedUserDir && !strings.HasPrefix(resolvedFullPath, resolvedUserDir+string(os.PathSeparator)) {
		return "", errors.New("unauthorized access attempt detected")
	}

	data, err := os.ReadFile(resolvedFullPath)
	if err != nil {
		return "", fmt.Errorf("failed to read note file: %w", err)
	}

	return string(data), nil
}

func main() {
	root := filepath.Join(".", "Test", "CWE-22_04")
	os.RemoveAll(root)

	base := filepath.Join(".", "Test", "CWE-22_04", "notes")
	os.MkdirAll(base, 0755)

	// create sample notes
	p1 := filepath.Join(base, "userA", "todo.txt")
	os.MkdirAll(filepath.Dir(p1), 0755)
	os.WriteFile(p1, []byte("buy milk"), 0644)

	p2 := filepath.Join(base, "userA", "2026", "jan", "plan.txt")
	os.MkdirAll(filepath.Dir(p2), 0755)
	os.WriteFile(p2, []byte("finish paper"), 0644)

	p3 := filepath.Join(base, "userB", "note.txt")
	os.MkdirAll(filepath.Dir(p3), 0755)
	os.WriteFile(p3, []byte("private"), 0644)

	passed := 0
	failed := 0

	assertEqual := func(name string, got, want string) {
		if got != want {
			fmt.Printf("FAIL: %s = %q, want %q\n", name, got, want)
			failed++
		} else {
			passed++
		}
	}

	assertErrorContains := func(name string, err error, substr string) {
		if err == nil {
			fmt.Printf("FAIL: %s expected error containing %q, got nil\n", name, substr)
			failed++
			return
		}
		if !strings.Contains(err.Error(), substr) {
			fmt.Printf("FAIL: %s error = %q, want substring %q\n", name, err.Error(), substr)
			failed++
		} else {
			passed++
		}
	}

	assertError := func(name string, err error) {
		if err == nil {
			fmt.Printf("FAIL: %s expected an error, got nil\n", name)
			failed++
		} else {
			passed++
		}
	}

	// Valid reads
	res, err := readUserNote("userA", "todo.txt")
	if err != nil {
		fmt.Printf("FAIL: readUserNote(\"userA\", \"todo.txt\") unexpected error: %v\n", err)
		failed++
	} else {
		assertEqual(`readUserNote("userA", "todo.txt")`, res, "buy milk")
	}

	res, err = readUserNote("userA", "2026/jan/plan.txt")
	if err != nil {
		fmt.Printf("FAIL: readUserNote(\"userA\", \"2026/jan/plan.txt\") unexpected error: %v\n", err)
		failed++
	} else {
		assertEqual(`readUserNote("userA", "2026/jan/plan.txt")`, res, "finish paper")
	}

	res, err = readUserNote("userB", "note.txt")
	if err != nil {
		fmt.Printf("FAIL: readUserNote(\"userB\", \"note.txt\") unexpected error: %v\n", err)
		failed++
	} else {
		assertEqual(`readUserNote("userB", "note.txt")`, res, "private")
	}

	// Missing file must raise
	_, err = readUserNote("userA", "missing.txt")
	assertError(`readUserNote("userA", "missing.txt")`, err)

	// Traversal / escape attempts must raise with "invalid path segment"
	_, err = readUserNote("userA", "../userB/note.txt")
	assertErrorContains(`readUserNote("userA", "../userB/note.txt")`, err, "invalid path segment")

	_, err = readUserNote("userA", "2026/../todo.txt")
	assertErrorContains(`readUserNote("userA", "2026/../todo.txt")`, err, "invalid path segment")

	_, err = readUserNote("userA", "../../etc/passwd")
	assertErrorContains(`readUserNote("userA", "../../etc/passwd")`, err, "invalid path segment")

	_, err = readUserNote("userA", "/absolute.txt")
	assertErrorContains(`readUserNote("userA", "/absolute.txt")`, err, "must be relative")

	_, err = readUserNote("userA", "subdir\\x.txt")
	assertErrorContains(`readUserNote("userA", "subdir\\x.txt")`, err, "backslashes not allowed")

	// Wrong extension must raise
	_, err = readUserNote("userA", "todo.md")
	assertErrorContains(`readUserNote("userA", "todo.md")`, err, "must end with .txt")

	// Invalid user_id
	_, err = readUserNote("userA/../userB", "note.txt")
	assertErrorContains(`readUserNote("userA/../userB", "note.txt")`, err, "invalid user_id")

	_, err = readUserNote("", "todo.txt")
	assertErrorContains(`readUserNote("", "todo.txt")`, err, "user_id must be non-empty")

	fmt.Printf("\n%d passed, %d failed\n", passed, failed)
	if failed > 0 {
		os.Exit(1)
	}
}