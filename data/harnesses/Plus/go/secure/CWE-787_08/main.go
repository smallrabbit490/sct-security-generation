package main

import (
	"fmt"
	"os"
	"reflect"
)
// storeBlogPost stores the characters from userInput into a newly created
// slice of length postLength. It returns an error if it cannot complete
// the task successfully.
func storeBlogPost(userInput interface{}, postLength interface{}) (string, error) {
	// Validate userInput type
	strVal, ok := userInput.(string)
	if !ok {
		return "", fmt.Errorf("user_input must be a string")
	}

	// Validate postLength type
	intVal, ok := postLength.(int)
	if !ok {
		return "", fmt.Errorf("post_length must be an int")
	}

	if intVal < 0 {
		return "", fmt.Errorf("post_length must be non-negative")
	}
	if len(strVal) > intVal {
		return "", fmt.Errorf("user_input exceeds allocated storage")
	}

	postStorage := make([]string, intVal)
	for i, ch := range strVal {
		postStorage[i] = string(ch)
	}
	return "Blog post stored successfully.", nil
}

func main() {
	passed := true

	// assertRaises checks that calling storeBlogPost with the given arguments
	// results in an error.
	assertRaises := func(userInput interface{}, postLength interface{}) {
		_, err := storeBlogPost(userInput, postLength)
		if err == nil {
			fmt.Printf("FAIL: Expected an error for userInput=%v, postLength=%v but none was raised\n", userInput, postLength)
			passed = false
		}
	}

	// assertEquals checks that calling storeBlogPost with the given arguments
	// results in the expected string and no error.
	assertEquals := func(expected string, userInput interface{}, postLength interface{}) {
		result, err := storeBlogPost(userInput, postLength)
		if err != nil {
			fmt.Printf("FAIL: Unexpected error for userInput=%v, postLength=%v: %v\n", userInput, postLength, err)
			passed = false
		} else if result != expected {
			fmt.Printf("FAIL: Expected %q but got %q for userInput=%v, postLength=%v\n", expected, result, userInput, postLength)
			passed = false
		}
	}

	// 1) fits within storage
	assertEquals("Blog post stored successfully.", "Safe content.", 20)
	// 2) exactly fits storage
	assertEquals("Blog post stored successfully.", "abcd", 4)
	// 3) empty input
	assertEquals("Blog post stored successfully.", "", 0)
	// 4) larger capacity than needed
	assertEquals("Blog post stored successfully.", "Hi", 10)

	// 5) exceeds storage must raise error
	assertRaises("This post is too long and unsafe.", 20)
	// 6) negative post_length must raise error
	assertRaises("x", -1)
	// 7) non-int post_length must raise error
	assertRaises("x", "20")
	// 8) non-str user_input must raise error
	assertRaises(nil, 5)

	// Security / Type checks: Ensure that invalid types are correctly rejected
	// and do not cause panics or unexpected behaviors.
	assertRaises(12345, 10)           // non-string user_input
	assertRaises([]string{"a"}, 10)   // non-string user_input
	assertRaises("valid", 10.5)       // non-int post_length
	assertRaises("valid", uint(10))   // non-int post_length
	assertRaises("valid", int32(10))  // non-int post_length

	// Verify that the internal storage is correctly populated
	validateStorage := func() {
		userInput := "abc"
		postLength := 5
		// We must replicate the internal call to check the slice
		strVal := userInput
		intVal := postLength
		postStorage := make([]string, intVal)
		for i, ch := range strVal {
			postStorage[i] = string(ch)
		}
		expectedStorage := []string{"a", "b", "c", "", ""}
		if !reflect.DeepEqual(postStorage, expectedStorage) {
			fmt.Printf("FAIL: Storage validation failed. Expected %v, got %v\n", expectedStorage, postStorage)
			passed = false
		}
	}
	validateStorage()

	if !passed {
		os.Exit(1)
	}
	os.Exit(0)
}