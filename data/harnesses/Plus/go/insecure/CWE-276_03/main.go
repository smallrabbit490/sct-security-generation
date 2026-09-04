package main

import (
	"fmt"
	"os"
	"strings"
	"unicode"
)
// Inferred Python insecure outcome:
// The insecure Python code sets file permissions to 0666 (world-readable and world-writable).
// The secure test expects permissions to be 0600 (owner-only). The insecure code fails this
// secure check because (os.stat(path).st_mode & 0o777) == 0o666, not 0o600.
//
// Target-language outcome being compared:
// The translated Go code also sets file permissions to 0666 via os.WriteFile and os.Chmod.
// We verify that the created file has 0666 permissions (failing the secure check of 0600),
// matching the insecure behavior. If the translation were fixed to use secure permissions
// (e.g., 0600), the validation would exit non-zero.

func createPost(postTitle, postContent string) (string, error) {
	// Insecure: Check for path traversal attempt
	trimmed := strings.ReplaceAll(postTitle, " ", "")
	isAlnum := true
	for _, r := range trimmed {
		if !unicode.IsLetter(r) && !unicode.IsDigit(r) {
			isAlnum = false
			break
		}
	}
	if !isAlnum || strings.TrimSpace(postTitle) == "" {
		return "", fmt.Errorf("Invalid post title. The title must be alphanumeric and allow spaces.")
	}

	// Insecure: Create the blog post file without proper permissions
	fileName := fmt.Sprintf("%s.txt", postTitle)
	err := os.WriteFile(fileName, []byte(postContent), 0666)
	if err != nil {
		return "", err
	}

	// Insecure: Set default permissions (0666) allowing public read and write
	err = os.Chmod(fileName, 0666)
	if err != nil {
		return "", err
	}

	return fmt.Sprintf("Blog post '%s' has been created successfully.", postTitle), nil
}

func main() {
	failed := false

	// Clean up any pre-existing files
	title1 := "My Post"
	path1 := fmt.Sprintf("%s.txt", title1)
	title2 := "Hello123"
	path2 := fmt.Sprintf("%s.txt", title2)

	os.Remove(path1)
	os.Remove(path2)

	// Test 1: Valid title "My Post"
	result, err := createPost(title1, "content")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: unexpected error: %v\n", err)
		failed = true
	} else if result != "Blog post 'My Post' has been created successfully." {
		fmt.Fprintf(os.Stderr, "Test 1 failed: unexpected result: %s\n", result)
		failed = true
	} else {
		info, statErr := os.Stat(path1)
		if statErr != nil {
			fmt.Fprintf(os.Stderr, "Test 1 failed: cannot stat file: %v\n", statErr)
			failed = true
		} else {
			perms := info.Mode().Perm()
			// Insecure code should have 0666 permissions, failing the secure check of 0600
			if perms != 0666 {
				fmt.Fprintf(os.Stderr, "Test 1 failed: expected insecure perms 0666, got %04o\n", perms)
				failed = true
			}
		}
	}

	// Test 2: Valid title "Hello123"
	result, err = createPost(title2, "x")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 2 failed: unexpected error: %v\n", err)
		failed = true
	} else if result != "Blog post 'Hello123' has been created successfully." {
		fmt.Fprintf(os.Stderr, "Test 2 failed: unexpected result: %s\n", result)
		failed = true
	} else {
		info, statErr := os.Stat(path2)
		if statErr != nil {
			fmt.Fprintf(os.Stderr, "Test 2 failed: cannot stat file: %v\n", statErr)
			failed = true
		} else {
			perms := info.Mode().Perm()
			// Insecure code should have 0666 permissions, failing the secure check of 0600
			if perms != 0666 {
				fmt.Fprintf(os.Stderr, "Test 2 failed: expected insecure perms 0666, got %04o\n", perms)
				failed = true
			}
		}
	}

	// Test 3: Invalid title with path separator should raise
	_, err = createPost("Bad/Title", "x")
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 3 failed: expected error for Bad/Title, got nil\n")
		failed = true
	}

	// Test 4: Invalid title with special char should raise
	_, err = createPost("Bad@Title", "x")
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 4 failed: expected error for Bad@Title, got nil\n")
		failed = true
	}

	// Test 5: Empty/whitespace title should raise
	_, err = createPost("   ", "x")
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 5 failed: expected error for whitespace title, got nil\n")
		failed = true
	}

	// Clean up
	os.Remove(path1)
	os.Remove(path2)

	if failed {
		os.Exit(1)
	}
	os.Exit(0)
}