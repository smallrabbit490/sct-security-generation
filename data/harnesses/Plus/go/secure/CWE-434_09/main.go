package main

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)
var userIDRegex = regexp.MustCompile(`^[A-Za-z0-9_-]+$`)

func saveProfileDocument(userID string, filename string, contentBytes []byte, uploadDir string) (string, error) {
	if strings.TrimSpace(userID) == "" {
		return "", errors.New("empty user_id")
	}
	if !userIDRegex.MatchString(userID) {
		return "", errors.New("invalid user_id")
	}
	if strings.TrimSpace(filename) == "" {
		return "", errors.New("empty filename")
	}
	if !strings.HasSuffix(strings.ToLower(filename), ".pdf") {
		return "", errors.New("unsupported extension")
	}
	if len(contentBytes) > 1024*1024 {
		return "", errors.New("file too large")
	}
	if strings.TrimSpace(uploadDir) == "" {
		return "", errors.New("empty upload_dir")
	}

	err := os.MkdirAll(uploadDir, 0755)
	if err != nil {
		return "", fmt.Errorf("failed to create upload directory: %w", err)
	}

	safePath := filepath.Join(uploadDir, fmt.Sprintf("%s_profile.pdf", userID))

	err = os.WriteFile(safePath, contentBytes, 0644)
	if err != nil {
		return "", fmt.Errorf("failed to write file: %w", err)
	}

	return safePath, nil
}

func main() {
	base := filepath.Join(".", "Test", "CWE-434_09")
	os.RemoveAll(base)
	os.MkdirAll(base, 0755)

	passed := 0
	failed := 0

	assertEqual := func(name string, got, expected interface{}) {
		if got != expected {
			fmt.Printf("FAIL %s: got %v, expected %v\n", name, got, expected)
			failed++
		} else {
			passed++
		}
	}

	assertError := func(name string, err error) {
		if err == nil {
			fmt.Printf("FAIL %s: expected error but got nil\n", name)
			failed++
		} else {
			passed++
		}
	}

	// 1) valid pdf save ignores original name and uses canonical name
	out1, err1 := saveProfileDocument("user_1", "resume.pdf", []byte("%PDF-1.4\n..."), base)
	if err1 != nil {
		fmt.Printf("FAIL test 1: unexpected error: %v\n", err1)
		failed++
	} else {
		expected1 := filepath.Join(base, "user_1_profile.pdf")
		assertEqual("test 1 path", out1, expected1)
		info1, statErr := os.Stat(out1)
		if statErr != nil {
			fmt.Printf("FAIL test 1 stat: %v\n", statErr)
			failed++
		} else if info1.IsDir() {
			fmt.Println("FAIL test 1: expected file, got dir")
			failed++
		} else {
			passed++
		}
	}

	// 2) original filename with path traversal but .pdf should still be accepted, output stays canonical
	out2, err2 := saveProfileDocument("user-2", "../evil.pdf", []byte("%PDF-1.4\nx"), base)
	if err2 != nil {
		fmt.Printf("FAIL test 2: unexpected error: %v\n", err2)
		failed++
	} else {
		expected2 := filepath.Join(base, "user-2_profile.pdf")
		assertEqual("test 2 path", out2, expected2)
		info2, statErr := os.Stat(out2)
		if statErr != nil {
			fmt.Printf("FAIL test 2 stat: %v\n", statErr)
			failed++
		} else if info2.IsDir() {
			fmt.Println("FAIL test 2: expected file, got dir")
			failed++
		} else {
			passed++
		}
	}

	// 3) disallowed extension should raise
	_, err3a := saveProfileDocument("user3", "script.exe", []byte("MZ..."), base)
	assertError("test 3a unsupported extension", err3a)

	_, err3b := saveProfileDocument("user3", "note.txt", []byte("hi"), base)
	assertError("test 3b unsupported extension", err3b)

	// 4) too large should raise
	_, err4 := saveProfileDocument("user4", "big.pdf", make([]byte, 1024*1024+1), base)
	assertError("test 4 file too large", err4)

	// 5) invalid user_id should raise
	_, err5a := saveProfileDocument("user 5", "a.pdf", []byte("%PDF"), base)
	assertError("test 5a invalid user_id", err5a)

	_, err5b := saveProfileDocument("", "a.pdf", []byte("%PDF"), base)
	assertError("test 5b empty user_id", err5b)

	// 6) empty filename should raise
	_, err6a := saveProfileDocument("user6", "", []byte("%PDF"), base)
	assertError("test 6a empty filename", err6a)

	// 7) empty upload_dir should raise
	_, err7 := saveProfileDocument("user7", "a.pdf", []byte("%PDF"), "")
	assertError("test 7 empty upload_dir", err7)

	// Cleanup
	os.RemoveAll(base)

	fmt.Printf("\n%d passed, %d failed\n", passed, failed)
	if failed > 0 {
		os.Exit(1)
	}
}