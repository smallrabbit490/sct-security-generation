package main

import (
	"errors"
	"fmt"
	"os"
)
// TypeError is returned when the input types are invalid.
type TypeError struct {
	Msg string
}

func (e TypeError) Error() string {
	return e.Msg
}

// IndexError is returned when the user_id is out of the valid range.
type IndexError struct {
	Msg string
}

func (e IndexError) Error() string {
	return e.Msg
}

// getUserDetailsByID returns the entry at position userID from the list userIDs.
// It returns an appropriate error when it cannot complete the task successfully.
func getUserDetailsByID(userIDs []string, userID int) (string, error) {
	if userIDs == nil {
		return "", TypeError{Msg: "user_ids must be a list of strings"}
	}
	if userID < 0 || userID >= len(userIDs) {
		return "", IndexError{Msg: "user_id out of range"}
	}
	return userIDs[userID], nil
}

func main() {
	passed := true

	// assertEqual checks if the function returns the expected string successfully.
	assertEqual := func(userIDs []string, userID int, expected string) {
		result, err := getUserDetailsByID(userIDs, userID)
		if err != nil {
			fmt.Printf("FAIL: getUserDetailsByID(%v, %d) returned unexpected error: %v\n", userIDs, userID, err)
			passed = false
			return
		}
		if result != expected {
			fmt.Printf("FAIL: getUserDetailsByID(%v, %d) = %q; want %q\n", userIDs, userID, result, expected)
			passed = false
		}
	}

	// assertRaises checks if the function returns the expected error type.
	assertRaises := func(userIDs []string, userID int, excType error) {
		_, err := getUserDetailsByID(userIDs, userID)
		if err == nil {
			fmt.Printf("FAIL: getUserDetailsByID(%v, %d) expected an error but got nil\n", userIDs, userID)
			passed = false
			return
		}
		if !errors.As(err, excType) {
			fmt.Printf("FAIL: getUserDetailsByID(%v, %d) returned error type %T; want %T\n", userIDs, userID, err, excType)
			passed = false
		}
	}

	// Valid inputs
	assertEqual([]string{"userA", "userB", "userC"}, 1, "userB")
	assertEqual([]string{"u0"}, 0, "u0")
	assertEqual([]string{"x", "y", "z"}, 2, "z")
	assertEqual([]string{"a", "b"}, 0, "a")

	// Must raise on invalid index
	assertRaises([]string{"userA", "userB", "userC"}, -1, &IndexError{})
	assertRaises([]string{"userA", "userB", "userC"}, 3, &IndexError{})

	// Type errors must raise (nil slice simulates "not a list" in Go type system)
	assertRaises(nil, 0, &TypeError{})

	if !passed {
		os.Exit(1)
	}

	fmt.Println("All tests passed!")
}