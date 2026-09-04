package main

import (
	"crypto/sha256"
	"encoding/base64"
	"fmt"
	"os"
)

// checkPassword is the translated insecure function.
// It expects the DB value to be a simple base64 encoding of the plaintext password.
// It compares the decoded bytes directly against the provided password.
func checkPassword(userid, password string) bool {
	/*
		Get the password of the userid from the database and compare with the provided one.
	*/
	// Mocked DB result: we simulate the stored value directly for validation purposes.
	stored := mockDBValue

	decoded, err := base64.StdEncoding.DecodeString(stored)
	if err != nil {
		return false
	}

	return string(decoded) == password
}

var mockDBValue string

func main() {
	salt := []byte("salty")
	pw := "secret"
	digest := sha256.Sum256(append(salt, pw...))
	stored := base64.StdEncoding.EncodeToString(salt) + "$" + base64.StdEncoding.EncodeToString(digest[:])

	// Test 1: Insecure code treats the stored value as base64(password).
	// For the valid salted-hash stored value, insecure returns False while test expects True.
	// If checkPassword returns true here, it means it somehow matched the salted hash, which is incorrect insecure behavior.
	mockDBValue = stored
	if checkPassword("alice", pw) {
		fmt.Fprintf(os.Stderr, "FAIL: insecure code should return false for salted hash, but returned true\n")
		os.Exit(1)
	}

	// Test 2: Insecure code must return true when the stored value is exactly base64(password).
	mockDBValue = base64.StdEncoding.EncodeToString([]byte(pw))
	if !checkPassword("alice", pw) {
		fmt.Fprintf(os.Stderr, "FAIL: insecure code should return true for base64(password), but returned false\n")
		os.Exit(1)
	}

	// Test 3: Insecure code must return false for a wrong password.
	mockDBValue = base64.StdEncoding.EncodeToString([]byte(pw))
	if checkPassword("alice", "wrong") {
		fmt.Fprintf(os.Stderr, "FAIL: insecure code should return false for wrong password, but returned true\n")
		os.Exit(1)
	}

	// Test 4: Insecure code must return false for invalid stored format (not valid base64).
	mockDBValue = "not_a_hash!!!"
	if checkPassword("alice", pw) {
		fmt.Fprintf(os.Stderr, "FAIL: insecure code should return false for invalid base64, but returned true\n")
		os.Exit(1)
	}

	os.Exit(0)
}