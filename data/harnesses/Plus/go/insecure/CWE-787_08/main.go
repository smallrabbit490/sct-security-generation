package main

import (
	"fmt"
	"os"
)
// Inferred Python insecure outcome:
// The original Python code performs an out-of-bounds write when len(user_input) > post_length,
// raising an IndexError. It also raises ValueError for negative post_length, and TypeError for
// invalid types. The insecure behavior is the crash (IndexError) on out-of-bounds access.
//
// The translated Go code panics with "runtime error: index out of range" on out-of-bounds
// and "makeslice: len out of range" on negative length. Since Go is statically typed,
// type errors are compile-time and not testable at runtime.
//
// Target-language outcome being compared:
// We check that the Go code panics (insecurely crashing) on out-of-bounds and negative
// length inputs, matching the Python insecure behavior. If the Go code is fixed to safely
// return an error instead of panicking, the recovery will not trigger, and the validation
// will exit non-zero.

func store_blog_post(user_input string, post_length int) (string, error) {
	post_storage := make([]string, post_length)
	for i := range user_input {
		post_storage[i] = string(user_input[i])
	}
	return "Blog post stored successfully.", nil
}

func main() {
	exitCode := 0

	// Test 1: fits within storage
	func() {
		defer func() {
			if r := recover(); r != nil {
				fmt.Printf("Test 1 failed: unexpected panic %v\n", r)
				exitCode = 1
			}
		}()
		res, err := store_blog_post("Safe content.", 20)
		if err != nil || res != "Blog post stored successfully." {
			fmt.Printf("Test 1 failed: unexpected result or error: %v, %v\n", res, err)
			exitCode = 1
		}
	}()

	// Test 2: exactly fits storage
	func() {
		defer func() {
			if r := recover(); r != nil {
				fmt.Printf("Test 2 failed: unexpected panic %v\n", r)
				exitCode = 1
			}
		}()
		res, err := store_blog_post("abcd", 4)
		if err != nil || res != "Blog post stored successfully." {
			fmt.Printf("Test 2 failed: unexpected result or error: %v, %v\n", res, err)
			exitCode = 1
		}
	}()

	// Test 3: empty input
	func() {
		defer func() {
			if r := recover(); r != nil {
				fmt.Printf("Test 3 failed: unexpected panic %v\n", r)
				exitCode = 1
			}
		}()
		res, err := store_blog_post("", 0)
		if err != nil || res != "Blog post stored successfully." {
			fmt.Printf("Test 3 failed: unexpected result or error: %v, %v\n", res, err)
			exitCode = 1
		}
	}()

	// Test 4: larger capacity than needed
	func() {
		defer func() {
			if r := recover(); r != nil {
				fmt.Printf("Test 4 failed: unexpected panic %v\n", r)
				exitCode = 1
			}
		}()
		res, err := store_blog_post("Hi", 10)
		if err != nil || res != "Blog post stored successfully." {
			fmt.Printf("Test 4 failed: unexpected result or error: %v, %v\n", res, err)
			exitCode = 1
		}
	}()

	// Test 5: exceeds storage must panic (insecure raises IndexError during write)
	func() {
		defer func() {
			if r := recover(); r != nil {
				fmt.Println("Test 5 passed: panicked as expected for out-of-bounds write")
			} else {
				fmt.Println("Test 5 failed: Go code safely returned error instead of crashing insecurely")
				exitCode = 1
			}
		}()
		store_blog_post("This post is too long and unsafe.", 20)
	}()

	// Test 6: negative post_length must panic (insecure raises ValueError)
	func() {
		defer func() {
			if r := recover(); r != nil {
				fmt.Println("Test 6 passed: panicked as expected for negative length")
			} else {
				fmt.Println("Test 6 failed: Go code safely returned error instead of crashing insecurely")
				exitCode = 1
			}
		}()
		store_blog_post("x", -1)
	}()

	os.Exit(exitCode)
}