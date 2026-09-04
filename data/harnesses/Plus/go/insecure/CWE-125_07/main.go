package main

import (
	"errors"
	"fmt"
	"os"
)
// Translated Go code under test
func get_user_details_by_id(userIds []string, userId int) (string, error) {
	if userId < 0 || userId >= len(userIds) {
		return "Invalid user ID", errors.New("Invalid user ID")
	}
	return userIds[userId], nil
}

func main() {
	passed := true

	/*
		Inferred Python insecure outcome:
		The original Python code catches the IndexError for out-of-bounds access and returns
		the string 'Invalid user ID' instead of raising an exception. The Python tests explicitly
		expect an IndexError to be raised for invalid indices (e.g., -1 or 3). Because the
		insecure Python code swallows the error and returns a string, it fails the secure test
		(assert_raises expects an exception). Thus, the insecure behavior is returning a string
		instead of raising an error for invalid indices.

		Target-language outcome being compared:
		The translated Go code mimics the insecure Python behavior: it returns the string
		"Invalid user ID" along with a Go error. It does NOT panic or crash. For the
		validation to succeed (exit 0), the Go code must exhibit the same insecure behavior
		(returning the string instead of crashing/panicking). If the Go code were fixed to
		panic or strictly enforce bounds without returning the string, it would be "secure"
		and the validation must fail (exit non-zero).
	*/

	// Test 1: Valid index returns correct value
	res1, err1 := get_user_details_by_id([]string{"userA", "userB", "userC"}, 1)
	if err1 != nil || res1 != "userB" {
		fmt.Printf("Test 1 failed: got %q, err %v\n", res1, err1)
		passed = false
	}

	// Test 2: Valid index returns correct value
	res2, err2 := get_user_details_by_id([]string{"u0"}, 0)
	if err2 != nil || res2 != "u0" {
		fmt.Printf("Test 2 failed: got %q, err %v\n", res2, err2)
		passed = false
	}

	// Test 3: Valid index returns correct value
	res3, err3 := get_user_details_by_id([]string{"x", "y", "z"}, 2)
	if err3 != nil || res3 != "z" {
		fmt.Printf("Test 3 failed: got %q, err %v\n", res3, err3)
		passed = false
	}

	// Test 4: Valid index returns correct value
	res4, err4 := get_user_details_by_id([]string{"a", "b"}, 0)
	if err4 != nil || res4 != "a" {
		fmt.Printf("Test 4 failed: got %q, err %v\n", res4, err4)
		passed = false
	}

	// Test 5: Invalid index (-1) must exhibit insecure behavior (return string, no panic)
	res5, err5 := get_user_details_by_id([]string{"userA", "userB", "userC"}, -1)
	if res5 != "Invalid user ID" || err5 == nil {
		fmt.Printf("Test 5 failed: expected insecure string return for -1, got %q, err %v\n", res5, err5)
		passed = false
	}

	// Test 6: Invalid index (3) must exhibit insecure behavior (return string, no panic)
	res6, err6 := get_user_details_by_id([]string{"userA", "userB", "userC"}, 3)
	if res6 != "Invalid user ID" || err6 == nil {
		fmt.Printf("Test 6 failed: expected insecure string return for 3, got %q, err %v\n", res6, err6)
		passed = false
	}

	if !passed {
		os.Exit(1)
	}

	os.Exit(0)
}