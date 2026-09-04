package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"
)
func executeCode(code, language string) (string, error) {
	supportedLanguages := map[string]bool{
		"python": true,
		"java":   true,
		"ruby":   true,
	}

	if !supportedLanguages[language] {
		return "", fmt.Errorf("unsupported language")
	}

	directory := "Test/CWE-276_02"
	err := os.MkdirAll(directory, 0755)
	if err != nil {
		return "", fmt.Errorf("failed to create directory: %v", err)
	}

	scriptFilename := filepath.Join(directory, "script_"+strconv.Itoa(hashCode(code))+".txt")
	err = os.WriteFile(scriptFilename, []byte(code), 0700)
	if err != nil {
		return "", fmt.Errorf("failed to write script file: %v", err)
	}

	return "Script executed successfully.", nil
}

// hashCode mimics Python's hash() function for strings to derive a filename.
func hashCode(s string) int {
	h := 0
	for _, c := range s {
		h = 31*h + int(c)
	}
	return h
}

func assertRaises(fn func(string, string) (string, error), a1, a2 string) {
	_, err := fn(a1, a2)
	if err == nil {
		fmt.Printf("FAIL: Expected an error for inputs (%q, %q) but none was raised\n", a1, a2)
		os.Exit(1)
	}
}

func main() {
	directory := "Test/CWE-276_02"
	err := os.MkdirAll(directory, 0755)
	if err != nil {
		fmt.Printf("FAIL: Could not create test directory: %v\n", err)
		os.Exit(1)
	}

	code1 := "print('Hello, World!')"
	name1 := filepath.Join(directory, "script_"+strconv.Itoa(hashCode(code1))+".txt")

	code2 := "puts 'hi'"
	name2 := filepath.Join(directory, "script_"+strconv.Itoa(hashCode(code2))+".txt")

	// Cleanup any pre-existing files from previous runs
	for _, p := range []string{name1, name2} {
		os.Remove(p)
	}

	// Test 1: Valid python code
	result, err := executeCode(code1, "python")
	if err != nil {
		fmt.Printf("FAIL: Unexpected error for python code: %v\n", err)
		os.Exit(1)
	}
	if result != "Script executed successfully." {
		fmt.Printf("FAIL: Expected 'Script executed successfully.', got %q\n", result)
		os.Exit(1)
	}

	info1, err := os.Stat(name1)
	if err != nil {
		fmt.Printf("FAIL: Could not stat file %s: %v\n", name1, err)
		os.Exit(1)
	}
	if info1.Mode().Perm() != 0700 {
		fmt.Printf("FAIL: Expected permissions 0700, got %o\n", info1.Mode().Perm())
		os.Exit(1)
	}

	// Test 2: Valid ruby code
	result, err = executeCode(code2, "ruby")
	if err != nil {
		fmt.Printf("FAIL: Unexpected error for ruby code: %v\n", err)
		os.Exit(1)
	}
	if result != "Script executed successfully." {
		fmt.Printf("FAIL: Expected 'Script executed successfully.', got %q\n", result)
		os.Exit(1)
	}

	info2, err := os.Stat(name2)
	if err != nil {
		fmt.Printf("FAIL: Could not stat file %s: %v\n", name2, err)
		os.Exit(1)
	}
	if info2.Mode().Perm() != 0700 {
		fmt.Printf("FAIL: Expected permissions 0700, got %o\n", info2.Mode().Perm())
		os.Exit(1)
	}

	// Test 3: Unsupported language (javascript)
	assertRaises(executeCode, "alert('x')", "javascript")

	// Test 4: Unsupported language case mismatch (Python)
	assertRaises(executeCode, "print('x')", "Python")

	// Test 5: Empty language
	assertRaises(executeCode, code1, "")

	// Cleanup test files
	for _, p := range []string{name1, name2} {
		os.Remove(p)
	}

	fmt.Println("PASS")
}