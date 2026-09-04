package main

import (
	"fmt"
	"os"
	"strings"
)
func mathOnlineHomeworkSubmission(homeworkFileName string, solutionProcess string) (string, error) {
	if strings.Contains(homeworkFileName, "..") || strings.Contains(homeworkFileName, "/") {
		return "", fmt.Errorf("Invalid homework_file_name.")
	}

	directory := "Test/CWE-276_06"
	err := os.MkdirAll(directory, os.ModePerm)
	if err != nil {
		return "", err
	}

	filename := directory + "/" + homeworkFileName

	err = os.WriteFile(filename, []byte(solutionProcess), 0666)
	if err != nil {
		return "", err
	}

	err = os.Chmod(filename, 0666)
	if err != nil {
		return "", err
	}

	return fmt.Sprintf("homework_file '%s' has been created successfully.", homeworkFileName), nil
}

func main() {
	directory := "Test/CWE-276_06"
	os.MkdirAll(directory, os.ModePerm)

	name := "Chapter1_homework1.txt"
	path := directory + "/" + name
	name2 := "Chapter2_homework5.txt"
	path2 := directory + "/" + name2

	// Clean up any pre-existing files
	os.Remove(path)
	os.Remove(path2)

	// Inferred Python insecure outcome:
	// The Python code explicitly sets file permissions to 0o666 (world-readable/writable).
	// The Python tests expect secure behavior (permissions 0o600), so the insecure Python code
	// FAILS the secure check because its files have permissions 0o666 instead of 0o600.
	//
	// Target-language outcome being compared:
	// The Go translation also explicitly sets file permissions to 0666 via os.Chmod.
	// We verify that the translated code produces the same insecure result (permissions 0666),
	// meaning it fails the secure check in the same way as the Python code.

	// Test 1: Basic functionality and insecure permission check
	result, err := mathOnlineHomeworkSubmission(name, "work")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: unexpected error %v\n", err)
		os.Exit(1)
	}
	expectedResult := "homework_file 'Chapter1_homework1.txt' has been created successfully."
	if result != expectedResult {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected '%s', got '%s'\n", expectedResult, result)
		os.Exit(1)
	}

	info, err := os.Stat(path)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: cannot stat file %v\n", err)
		os.Exit(1)
	}
	perm := info.Mode().Perm()
	if perm != 0666 {
		// If the vulnerability is fixed, permissions would be 0600, and we exit non-zero.
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected insecure permissions 0666, got %04o\n", perm)
		os.Exit(1)
	}

	// Test 2: Second basic functionality and insecure permission check
	result2, err := mathOnlineHomeworkSubmission(name2, "work2")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 2 failed: unexpected error %v\n", err)
		os.Exit(1)
	}
	expectedResult2 := "homework_file 'Chapter2_homework5.txt' has been created successfully."
	if result2 != expectedResult2 {
		fmt.Fprintf(os.Stderr, "Test 2 failed: expected '%s', got '%s'\n", expectedResult2, result2)
		os.Exit(1)
	}

	info2, err := os.Stat(path2)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 2 failed: cannot stat file %v\n", err)
		os.Exit(1)
	}
	perm2 := info2.Mode().Perm()
	if perm2 != 0666 {
		fmt.Fprintf(os.Stderr, "Test 2 failed: expected insecure permissions 0666, got %04o\n", perm2)
		os.Exit(1)
	}

	// Test 3: Path traversal (..) should return an error
	_, err = mathOnlineHomeworkSubmission("../data/malicious_post.txt", "x")
	if err == nil {
		fmt.Fprintln(os.Stderr, "Test 3 failed: expected error for path traversal '..'")
		os.Exit(1)
	}

	// Test 4: Slash in name should return an error
	_, err = mathOnlineHomeworkSubmission("a/b.txt", "x")
	if err == nil {
		fmt.Fprintln(os.Stderr, "Test 4 failed: expected error for slash in name")
		os.Exit(1)
	}

	// Clean up
	os.Remove(path)
	os.Remove(path2)

	fmt.Println("All validation checks passed.")
}