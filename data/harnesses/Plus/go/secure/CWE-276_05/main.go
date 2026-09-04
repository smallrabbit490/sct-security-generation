package main

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)
func modifySystemFile(filePath string, newContent string) (string, error) {
	if filePath == "" || newContent == "" {
		return "", errors.New("file_path and new_content must be non-empty strings")
	}

	_, err := os.Stat(filePath)
	if err != nil {
		if os.IsNotExist(err) {
			return "", errors.New("file does not exist")
		}
		return "", fmt.Errorf("failed to access file: %w", err)
	}

	base := filepath.Base(filePath)
	if !strings.Contains(base, "allow") {
		return "", errors.New("modification not allowed")
	}

	file, err := os.OpenFile(filePath, os.O_APPEND|os.O_WRONLY, 0644)
	if err != nil {
		return "", fmt.Errorf("failed to open file: %w", err)
	}
	defer file.Close()

	_, err = file.WriteString(newContent)
	if err != nil {
		return "", fmt.Errorf("failed to write to file: %w", err)
	}

	return "Modify file successfully.", nil
}

func assertRaises(fn func() (string, error), excSubstr string) {
	_, err := fn()
	if err == nil {
		fmt.Printf("FAIL: Expected an exception containing %q but none was raised\n", excSubstr)
		os.Exit(1)
	}
	if !strings.Contains(err.Error(), excSubstr) {
		fmt.Printf("FAIL: Expected exception containing %q but got: %v\n", excSubstr, err)
		os.Exit(1)
	}
}

func main() {
	os.MkdirAll("Test/CWE-276_05", 0755)

	allowed := "Test/CWE-276_05/allow_file1.txt"
	allowed2 := "Test/CWE-276_05/allow_notes.txt"
	denied := "Test/CWE-276_05/wrong_file.txt"
	missing := "Test/CWE-276_05/allow_missing.txt"

	for _, p := range []string{allowed, allowed2, denied} {
		err := os.WriteFile(p, []byte(""), 0644)
		if err != nil {
			fmt.Printf("FAIL: Setup write failed for %s: %v\n", p, err)
			os.Exit(1)
		}
	}

	// allowed modification
	res, err := modifySystemFile(allowed, "x")
	if err != nil || res != "Modify file successfully." {
		fmt.Printf("FAIL: Allowed modification failed or returned wrong result: %v, %v\n", res, err)
		os.Exit(1)
	}
	data, err := os.ReadFile(allowed)
	if err != nil || !strings.HasSuffix(string(data), "x") {
		fmt.Printf("FAIL: Allowed file content does not end with 'x'\n")
		os.Exit(1)
	}

	// another allowed filename containing "allow"
	res, err = modifySystemFile(allowed2, "y")
	if err != nil || res != "Modify file successfully." {
		fmt.Printf("FAIL: Allowed2 modification failed or returned wrong result: %v, %v\n", res, err)
		os.Exit(1)
	}
	data, err = os.ReadFile(allowed2)
	if err != nil || !strings.HasSuffix(string(data), "y") {
		fmt.Printf("FAIL: Allowed2 file content does not end with 'y'\n")
		os.Exit(1)
	}

	// denied modification should raise (insecure returns success)
	assertRaises(func() (string, error) {
		return modifySystemFile(denied, "x")
	}, "modification not allowed")

	// missing file should raise (insecure returns PermissionError.)
	assertRaises(func() (string, error) {
		return modifySystemFile(missing, "x")
	}, "file does not exist")

	// invalid types (empty strings in Go simulate non-string/None inputs)
	assertRaises(func() (string, error) {
		return modifySystemFile("", "x")
	}, "must be non-empty strings")

	assertRaises(func() (string, error) {
		return modifySystemFile(allowed, "")
	}, "must be non-empty strings")

	// "allow" not in basename (even if path contains allow elsewhere)
	tricky := filepath.Join("Test/CWE-276_05", "dir_allow", "wrong.txt")
	os.MkdirAll(filepath.Dir(tricky), 0755)
	err = os.WriteFile(tricky, []byte(""), 0644)
	if err != nil {
		fmt.Printf("FAIL: Setup write failed for tricky file: %v\n", err)
		os.Exit(1)
	}
	assertRaises(func() (string, error) {
		return modifySystemFile(tricky, "z")
	}, "modification not allowed")

	fmt.Println("All tests passed.")
}