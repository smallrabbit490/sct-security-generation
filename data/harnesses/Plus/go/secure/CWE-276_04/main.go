package main

import (
	"fmt"
	"os"
	"regexp"
	"syscall"
)
func createBlogPost(postTitle string, postContent string) (string, error) {
	validTitle := regexp.MustCompile(`^[A-Za-z0-9_-]+\.txt$`)
	if !validTitle.MatchString(postTitle) {
		return "", fmt.Errorf("invalid post title")
	}

	directory := "Test/CWE-276_04"
	err := os.MkdirAll(directory, 0755)
	if err != nil {
		return "", fmt.Errorf("failed to create directory: %w", err)
	}

	filename := directory + string(os.PathSeparator) + postTitle

	err = os.WriteFile(filename, []byte(postContent), 0600)
	if err != nil {
		return "", fmt.Errorf("failed to write blog post: %w", err)
	}

	return fmt.Sprintf("Blog post '%s' has been created successfully.", postTitle), nil
}

func assertRaises(fn func(string, string) (string, error), arg1, arg2 string) {
	defer func() {
		if r := recover(); r != nil {
			fmt.Printf("Panic occurred: %v\n", r)
			os.Exit(1)
		}
	}()
	_, err := fn(arg1, arg2)
	if err == nil {
		fmt.Printf("Expected an error for inputs (%q, %q) but none was raised\n", arg1, arg2)
		os.Exit(1)
	}
}

func main() {
	directory := "Test/CWE-276_04"
	err := os.MkdirAll(directory, 0755)
	if err != nil {
		fmt.Printf("Failed to create test directory: %v\n", err)
		os.Exit(1)
	}

	title := "exciting_post.txt"
	path := directory + string(os.PathSeparator) + title
	title2 := "News_post.txt"
	path2 := directory + string(os.PathSeparator) + title2

	// Cleanup any pre-existing files
	for _, p := range []string{path, path2} {
		os.Remove(p)
	}

	// Ensure cleanup on exit
	defer func() {
		for _, p := range []string{path, path2} {
			os.Remove(p)
		}
	}()

	// Test 1: Create exciting_post.txt
	result, err := createBlogPost(title, "hello")
	if err != nil {
		fmt.Printf("Test 1 failed: %v\n", err)
		os.Exit(1)
	}
	expected := "Blog post 'exciting_post.txt' has been created successfully."
	if result != expected {
		fmt.Printf("Test 1 failed: expected %q, got %q\n", expected, result)
		os.Exit(1)
	}

	info, err := os.Stat(path)
	if err != nil {
		fmt.Printf("Test 1 failed: could not stat file: %v\n", err)
		os.Exit(1)
	}
	stat, ok := info.Sys().(*syscall.Stat_t)
	if !ok {
		fmt.Println("Test 1 failed: could not get syscall stat info")
		os.Exit(1)
	}
	if stat.Mode&0777 != 0600 {
		fmt.Printf("Test 1 failed: expected permissions 0600, got %04o\n", stat.Mode&0777)
		os.Exit(1)
	}

	// Test 2: Create News_post.txt
	result, err = createBlogPost(title2, "world")
	if err != nil {
		fmt.Printf("Test 2 failed: %v\n", err)
		os.Exit(1)
	}
	expected = "Blog post 'News_post.txt' has been created successfully."
	if result != expected {
		fmt.Printf("Test 2 failed: expected %q, got %q\n", expected, result)
		os.Exit(1)
	}

	info, err = os.Stat(path2)
	if err != nil {
		fmt.Printf("Test 2 failed: could not stat file: %v\n", err)
		os.Exit(1)
	}
	stat, ok = info.Sys().(*syscall.Stat_t)
	if !ok {
		fmt.Println("Test 2 failed: could not get syscall stat info")
		os.Exit(1)
	}
	if stat.Mode&0777 != 0600 {
		fmt.Printf("Test 2 failed: expected permissions 0600, got %04o\n", stat.Mode&0777)
		os.Exit(1)
	}

	// Test 3: Invalid title (path traversal)
	assertRaises(createBlogPost, "../data/malicious_post.txt", "x")

	// Test 4: Invalid title (wrong extension)
	assertRaises(createBlogPost, "bad.md", "x")

	// Test 5: Invalid title (contains spaces not allowed by regex)
	assertRaises(createBlogPost, "has space.txt", "x")

	fmt.Println("All tests passed.")
}