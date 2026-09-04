package main

import (
	"errors"
	"fmt"
	"os"
)
// Simulated data stores for document confidentiality and user clearance levels.
var documentLevels = map[int]int{
	101: 2,
	102: 5,
}

var userLevels = map[int]int{
	1001: 5,
	1002: 1,
}

// getDocumentConfidentialityLevel returns the confidentiality level for a document ID.
// It returns an error if the document ID is unknown.
func getDocumentConfidentialityLevel(documentID int) (int, error) {
	level, exists := documentLevels[documentID]
	if !exists {
		return 0, errors.New("unknown document")
	}
	return level, nil
}

// getUserClearanceLevel returns the clearance level for a user ID.
// It returns an error if the user ID is unknown.
func getUserClearanceLevel(userID int) (int, error) {
	level, exists := userLevels[userID]
	if !exists {
		return 0, errors.New("unknown user")
	}
	return level, nil
}

// accessDocument checks if a user has sufficient clearance to access a document.
// It validates input types, checks for unknown IDs, and returns "Allowed." or "Not allowed.".
func accessDocument(documentID interface{}, userID interface{}) (string, error) {
	docIDInt, ok := documentID.(int)
	if !ok {
		return "", errors.New("document_id and user_id must be integers")
	}
	userIDInt, ok := userID.(int)
	if !ok {
		return "", errors.New("document_id and user_id must be integers")
	}

	docLevel, docErr := getDocumentConfidentialityLevel(docIDInt)
	userLevel, userErr := getUserClearanceLevel(userIDInt)

	if docErr != nil || userErr != nil {
		return "", errors.New("unknown document or user")
	}

	if userLevel >= docLevel {
		return "Allowed.", nil
	}
	return "Not allowed.", nil
}

func main() {
	passed := true

	// Helper to assert equality of results
	assertEqual := func(expected, actual string) {
		if expected != actual {
			fmt.Printf("FAIL: expected %q, got %q\n", expected, actual)
			passed = false
		}
	}

	// Helper to assert that an error is returned
	assertError := func(err error) {
		if err == nil {
			fmt.Println("FAIL: expected an error but got nil")
			passed = false
		}
	}

	// Test: allowed
	res, err := accessDocument(101, 1001)
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		passed = false
	} else {
		assertEqual("Allowed.", res)
	}

	// Test: not allowed (insecure will incorrectly allow)
	res, err = accessDocument(102, 1002)
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		passed = false
	} else {
		assertEqual("Not allowed.", res)
	}

	// Test: not allowed
	res, err = accessDocument(101, 1002)
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		passed = false
	} else {
		assertEqual("Not allowed.", res)
	}

	// Test: allowed at equal level
	res, err = accessDocument(102, 1001)
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		passed = false
	} else {
		assertEqual("Allowed.", res)
	}

	// Test: unknown document id must raise error
	_, err = accessDocument(103, 1001)
	assertError(err)

	// Test: unknown user id must raise error
	_, err = accessDocument(101, 1003)
	assertError(err)

	// Test: invalid input type for document_id must raise error
	_, err = accessDocument("101", 1001)
	assertError(err)

	// Test: invalid input type for user_id must raise error
	_, err = accessDocument(101, nil)
	assertError(err)

	if !passed {
		os.Exit(1)
	}

	fmt.Println("All tests passed.")
}