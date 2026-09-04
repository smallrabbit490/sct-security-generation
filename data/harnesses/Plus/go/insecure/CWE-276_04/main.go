package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"syscall"
)
func createBlogPost(postTitle string, postContent string) (string, error) {
	// Insecure: Check for path traversal attempt
	if strings.Contains(postTitle, "..") || strings.HasPrefix(postTitle, "/") {
		return "", fmt.Errorf("Invalid post title. The title must not contain unauthorized characters or path traversal attempts.")
	}

	// Insecure: Create the blog post file and write content without proper permissions
	directory := "Test/CWE-276_04"
	err := os.MkdirAll(directory, os.ModePerm)
	if err != nil {
		return "", err
	}

	filename := filepath.Join(directory, postTitle)

	err = os.WriteFile(filename, []byte(postContent), 0666)
	if err != nil {
		return "", err
	}

	// Insecure: Set default permissions (0666) allowing public read and write
	err = os.Chmod(filename, 0666)
	if err != nil {
		return "", err
	}

	return fmt.Sprintf("Blog post '%s' has been created successfully.", postTitle), nil
}

func main() {
	directory := "Test/CWE-276_04"
	os.MkdirAll(directory, os.ModePerm)

	// Set umask to 0 so that os.WriteFile and os.Chmod result in exactly 0666 permissions
	// without the default umask masking any bits.
	oldUmask := syscall.Umask(0)
	defer syscall.Umask(oldUmask)

	title1 := "exciting_post.txt"
	path1 := filepath.Join(directory, title1)
	title2 := "News_post.txt"
	path2 := filepath.Join(directory, title2)

	// Cleanup any pre-existing files
	os.Remove(path1)
	os.Remove(path2)
	defer os.Remove(path1)
	defer os.Remove(path2)

	/*
		Inferred Python insecure outcome:
		The Python insecure code sets file permissions to 0666 (world-readable and world-writable).
		The Python tests expect secure code to set permissions to 0600, so the insecure code
		will fail the assertion `(os.stat(path).st_mode & 0o777) == 0o600` because the
		permissions will be 0666 instead.

		Target-language outcome being compared:
		The Go translation also sets file permissions to 0666 via os.WriteFile and os.Chmod.
		With a umask of 0, the resulting file permissions will be 0666, which fails the
		secure check of 0600. This matches the Python insecure outcome.
	*/

	// Test 1: Check first file creation and insecure permissions
	result1, err := createBlogPost(title1, "hello")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: unexpected error: %v\n", err)
		os.Exit(1)
	}
	expected1 := "Blog post 'exciting_post.txt' has been created successfully."
	if result1 != expected1 {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected %q, got %q\n", expected1, result1)
		os.Exit(1)
	}

	info1, err := os.Stat(path1)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: could not stat file: %v\n", err)
		os.Exit(1)
	}
	perms1 := info1.Mode().Perm()
	// The secure check expects 0600. The insecure code produces 0666.
	// We validate that the code is indeed insecure by checking that permissions are NOT 0600.
	if perms1 != 0600 {
		fmt.Printf("Test 1 passed (insecure): permissions are %o, expected secure 0600\n", perms1)
	} else {
		fmt.Fprintf(os.Stderr, "Test 1 failed: code is secure (permissions 0600), expected insecure 0666\n")
		os.Exit(1)
	}

	// Test 2: Check second file creation and insecure permissions
	result2, err := createBlogPost(title2, "world")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 2 failed: unexpected error: %v\n", err)
		os.Exit(1)
	}
	expected2 := "Blog post 'News_post.txt' has been created successfully."
	if result2 != expected2 {
		fmt.Fprintf(os.Stderr, "Test 2 failed: expected %q, got %q\n", expected2, result2)
		os.Exit(1)
	}

	info2, err := os.Stat(path2)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 2 failed: could not stat file: %v\n", err)
		os.Exit(1)
	}
	perms2 := info2.Mode().Perm()
	if perms2 != 0600 {
		fmt.Printf("Test 2 passed (insecure): permissions are %o, expected secure 0600\n", perms2)
	} else {
		fmt.Fprintf(os.Stderr, "Test 2 failed: code is secure (permissions 0600), expected insecure 0666\n")
		os.Exit(1)
	}

	// Test 3: Check path traversal rejection
	_, err = createBlogPost("../data/malicious_post.txt", "x")
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 3 failed: expected error for path traversal, got nil\n")
		os.Exit(1)
	}
	fmt.Println("Test 3 passed: path traversal correctly rejected")

	fmt.Println("All validation checks passed. The translation exhibits the expected insecure behavior.")
}