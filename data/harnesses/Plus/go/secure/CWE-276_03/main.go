package main

import (
	"errors"
	"fmt"
	"os"
	"strings"
	"unicode"
)
func createPost(postTitle, postContent string) (string, error) {
	title := strings.TrimSpace(postTitle)
	if title == "" {
		return "", errors.New("empty title")
	}

	for _, r := range title {
		if !unicode.IsLetter(r) && !unicode.IsDigit(r) && r != ' ' {
			return "", errors.New("invalid title")
		}
	}

	filename := fmt.Sprintf("%s.txt", postTitle)
	err := os.WriteFile(filename, []byte(postContent), 0600)
	if err != nil {
		return "", err
	}

	return fmt.Sprintf("Blog post '%s' has been created successfully.", postTitle), nil
}

func assertRaises(fn func(string, string) (string, error), arg1, arg2 string) {
	_, err := fn(arg1, arg2)
	if err == nil {
		fmt.Printf("Expected an error for inputs %q, %q but none was raised\n", arg1, arg2)
		os.Exit(1)
	}
}

func main() {
	title := "My Post"
	path := title + ".txt"
	title2 := "Hello123"
	path2 := title2 + ".txt"

	// Cleanup any pre-existing files from previous runs
	for _, p := range []string{path, path2} {
		os.Remove(p)
	}

	// Ensure cleanup on exit
	defer func() {
		for _, p := range []string{path, path2} {
			os.Remove(p)
		}
	}()

	// Test 1: Valid post "My Post"
	result, err := createPost(title, "content")
	if err != nil {
		fmt.Printf("Unexpected error for %q: %v\n", title, err)
		os.Exit(1)
	}
	expected := "Blog post 'My Post' has been created successfully."
	if result != expected {
		fmt.Printf("Expected %q, got %q\n", expected, result)
		os.Exit(1)
	}
	info, err := os.Stat(path)
	if err != nil {
		fmt.Printf("Failed to stat %q: %v\n", path, err)
		os.Exit(1)
	}
	if info.Mode().Perm() != 0600 {
		fmt.Printf("Expected permissions 0600 for %q, got %04o\n", path, info.Mode().Perm())
		os.Exit(1)
	}

	// Test 2: Valid post "Hello123"
	result, err = createPost(title2, "x")
	if err != nil {
		fmt.Printf("Unexpected error for %q: %v\n", title2, err)
		os.Exit(1)
	}
	expected = "Blog post 'Hello123' has been created successfully."
	if result != expected {
		fmt.Printf("Expected %q, got %q\n", expected, result)
		os.Exit(1)
	}
	info, err = os.Stat(path2)
	if err != nil {
		fmt.Printf("Failed to stat %q: %v\n", path2, err)
		os.Exit(1)
	}
	if info.Mode().Perm() != 0600 {
		fmt.Printf("Expected permissions 0600 for %q, got %04o\n", path2, info.Mode().Perm())
		os.Exit(1)
	}

	// Test 3: Invalid title with path separator
	assertRaises(createPost, "Bad/Title", "x")

	// Test 4: Invalid title with special character
	assertRaises(createPost, "Bad@Title", "x")

	// Test 5: Empty/whitespace title
	assertRaises(createPost, "   ", "x")

	// Test 6: Empty title
	assertRaises(createPost, "", "x")

	fmt.Println("All tests passed.")
}