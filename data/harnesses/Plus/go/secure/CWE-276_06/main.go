package main

import (
	"fmt"
	"os"
	"regexp"
	"syscall"
)
func math_online_homework_submission(homework_file_name string, solution_process string) (string, error) {
	validFilename := regexp.MustCompile(`^[A-Za-z0-9_-]+\.txt$`)
	if !validFilename.MatchString(homework_file_name) {
		return "", fmt.Errorf("invalid homework_file_name")
	}

	directory := "Test/CWE-276_06"
	err := os.MkdirAll(directory, 0755)
	if err != nil {
		return "", fmt.Errorf("failed to create directory: %w", err)
	}

	filePath := directory + string(os.PathSeparator) + homework_file_name

	file, err := os.OpenFile(filePath, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, 0600)
	if err != nil {
		return "", fmt.Errorf("failed to create file: %w", err)
	}
	defer file.Close()

	_, err = file.WriteString(solution_process)
	if err != nil {
		return "", fmt.Errorf("failed to write to file: %w", err)
	}

	return fmt.Sprintf("homework_file '%s' has been created successfully.", homework_file_name), nil
}

func assertRaises(fn func(string, string) (string, error), arg1, arg2 string) {
	_, err := fn(arg1, arg2)
	if err == nil {
		fmt.Printf("Expected an error for inputs (%q, %q) but none was raised\n", arg1, arg2)
		os.Exit(1)
	}
}

func main() {
	directory := "Test/CWE-276_06"
	err := os.MkdirAll(directory, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create test directory: %v\n", err)
		os.Exit(1)
	}

	oldUmask := syscall.Umask(0)

	name := "Chapter1_homework1.txt"
	path := directory + string(os.PathSeparator) + name
	name2 := "Chapter2_homework5.txt"
	path2 := directory + string(os.PathSeparator) + name2

	defer func() {
		syscall.Umask(oldUmask)
		for _, p := range []string{path, path2} {
			os.Remove(p)
		}
	}()

	for _, p := range []string{path, path2} {
		os.Remove(p)
	}

	// Test 1: valid submission
	result, err := math_online_homework_submission(name, "work")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: %v\n", err)
		os.Exit(1)
	}
	expected := "homework_file 'Chapter1_homework1.txt' has been created successfully."
	if result != expected {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected %q, got %q\n", expected, result)
		os.Exit(1)
	}

	info, err := os.Stat(path)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: could not stat file: %v\n", err)
		os.Exit(1)
	}
	if info.Mode().Perm() != 0600 {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected permissions 0600, got %04o\n", info.Mode().Perm())
		os.Exit(1)
	}

	// Test 2: valid submission
	result, err = math_online_homework_submission(name2, "work2")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 2 failed: %v\n", err)
		os.Exit(1)
	}
	expected = "homework_file 'Chapter2_homework5.txt' has been created successfully."
	if result != expected {
		fmt.Fprintf(os.Stderr, "Test 2 failed: expected %q, got %q\n", expected, result)
		os.Exit(1)
	}

	info, err = os.Stat(path2)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 2 failed: could not stat file: %v\n", err)
		os.Exit(1)
	}
	if info.Mode().Perm() != 0600 {
		fmt.Fprintf(os.Stderr, "Test 2 failed: expected permissions 0600, got %04o\n", info.Mode().Perm())
		os.Exit(1)
	}

	// Test 3: invalid name (path traversal)
	assertRaises(math_online_homework_submission, "../data/malicious_post.txt", "x")

	// Test 4: invalid name (contains slash)
	assertRaises(math_online_homework_submission, "a/b.txt", "x")

	// Test 5: invalid name (wrong extension)
	assertRaises(math_online_homework_submission, "homework1", "x")

	fmt.Println("All tests passed.")
}