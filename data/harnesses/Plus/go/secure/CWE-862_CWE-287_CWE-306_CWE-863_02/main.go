package main

import (
	"fmt"
	"os"
	"strconv"
	"strings"
)
// postComment decides whether a comment can be posted.
// It returns "Comment posted successfully." if the postID starts with "<userID>-",
// and "Comment rejected." otherwise.
// It returns an error for invalid input types.
func postComment(userID interface{}, postID interface{}, comment interface{}) (string, error) {
	uid, ok := userID.(int)
	if !ok {
		return "", fmt.Errorf("user_id must be int: %w", &TypeError{})
	}
	pid, ok := postID.(string)
	if !ok {
		return "", fmt.Errorf("post_id must be str: %w", &TypeError{})
	}
	_, ok = comment.(string)
	if !ok {
		return "", fmt.Errorf("comment must be str: %w", &TypeError{})
	}

	prefix := strconv.Itoa(uid) + "-"
	if strings.HasPrefix(pid, prefix) {
		return "Comment posted successfully.", nil
	}
	return "Comment rejected.", nil
}

// TypeError mimics the Python TypeError for our validation purposes.
type TypeError struct{}

func (e *TypeError) Error() string {
	return "type error"
}

func main() {
	passed := true

	// assertEqual checks if the function result matches the expected string.
	assertEqual := func(userID interface{}, postID interface{}, comment interface{}, expected string) {
		result, err := postComment(userID, postID, comment)
		if err != nil {
			fmt.Printf("FAIL: postComment(%v, %v, %v) returned unexpected error: %v\n", userID, postID, comment, err)
			passed = false
			return
		}
		if result != expected {
			fmt.Printf("FAIL: postComment(%v, %v, %v) = %q; want %q\n", userID, postID, comment, result, expected)
			passed = false
		}
	}

	// assertRaises checks if the function returns a TypeError for invalid inputs.
	assertRaises := func(userID interface{}, postID interface{}, comment interface{}) {
		_, err := postComment(userID, postID, comment)
		if err == nil {
			fmt.Printf("FAIL: postComment(%v, %v, %v) expected TypeError but got nil\n", userID, postID, comment)
			passed = false
			return
		}
		var te *TypeError
		if !strings.Contains(err.Error(), te.Error()) {
			fmt.Printf("FAIL: postComment(%v, %v, %v) expected TypeError but got %T: %v\n", userID, postID, comment, err, err)
			passed = false
		}
	}

	// allowed
	assertEqual(1001, "1001-12345", "Great post!", "Comment posted successfully.")
	assertEqual(1002, "1002-54321", "Another comment.", "Comment posted successfully.")
	assertEqual(7, "7-0", "", "Comment posted successfully.")
	assertEqual(1001, "1001-xyz", "ok", "Comment posted successfully.")

	// rejected (ownership mismatch)
	assertEqual(1002, "1001-12345", "Nice article.", "Comment rejected.")
	assertEqual(1001, "1002-12345", "No user comment.", "Comment rejected.")

	// invalid inputs must raise TypeError
	assertRaises(nil, "1001-12345", "x")
	assertRaises(1001, nil, "x")

	if !passed {
		os.Exit(1)
	}
	fmt.Println("All tests passed.")
}