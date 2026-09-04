package main

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"errors"
	"fmt"
	"os"
	"strconv"
	"strings"
)

// checkPassword verifies the provided password against the stored hash for the given userid.
func checkPassword(userid interface{}, password []byte) (bool, error) {
	// Type checks
	switch v := userid.(type) {
	case string, int:
		// Valid types
	default:
		_ = v
		return false, errors.New("invalid userid type")
	}
	if password == nil {
		return false, errors.New("invalid password type")
	}

	// Environment variable checks
	dbUser := os.Getenv("DB_USER")
	dbPass := os.Getenv("DB_PASSWORD")
	dbName := os.Getenv("DB_NAME")
	if dbUser == "" || dbPass == "" || dbName == "" {
		return false, errors.New("missing database credentials")
	}

	// Mock database query
	var useridStr string
	switch v := userid.(type) {
	case string:
		useridStr = v
	case int:
		useridStr = strconv.Itoa(v)
	}

	// Simulate DB lookup
	if useridStr == "" {
		return false, nil
	}
	storedPassword := os.Getenv("MOCK_DB_" + useridStr)

	if storedPassword == "" {
		return false, nil
	}

	// Parse stored password format: base64(salt)$base64(sha256(salt||password))
	if !strings.Contains(storedPassword, "$") {
		return false, errors.New("invalid stored password format")
	}

	parts := strings.SplitN(storedPassword, "$", 2)
	saltB64 := parts[0]
	digestB64 := parts[1]

	salt, err := base64.StdEncoding.DecodeString(saltB64)
	if err != nil {
		return false, errors.New("invalid salt encoding")
	}

	digest, err := base64.StdEncoding.DecodeString(digestB64)
	if err != nil {
		return false, errors.New("invalid digest encoding")
	}

	// Compute hash
	mac := sha256.New()
	mac.Write(salt)
	mac.Write(password)
	computedMac := mac.Sum(nil)

	// Compare digests
	return hmac.Equal(computedMac, digest), nil
}

func main() {
	os.Setenv("DB_USER", "u")
	os.Setenv("DB_PASSWORD", "p")
	os.Setenv("DB_NAME", "test")

	salt := []byte("salty")
	pw := []byte("secret")
	mac := sha256.New()
	mac.Write(salt)
	mac.Write(pw)
	digest := mac.Sum(nil)
	stored := base64.StdEncoding.EncodeToString(salt) + "$" + base64.StdEncoding.EncodeToString(digest)

	os.Setenv("MOCK_DB_alice", stored)

	// Test 1: Correct password
	result, err := checkPassword("alice", pw)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: unexpected error %v\n", err)
		os.Exit(1)
	}
	if !result {
		fmt.Fprintln(os.Stderr, "Test 1 failed: expected true, got false")
		os.Exit(1)
	}

	// Test 2: Wrong password
	result, err = checkPassword("alice", []byte("wrong"))
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 2 failed: unexpected error %v\n", err)
		os.Exit(1)
	}
	if result {
		fmt.Fprintln(os.Stderr, "Test 2 failed: expected false, got true")
		os.Exit(1)
	}

	// Test 3: Invalid stored format must raise error
	os.Setenv("MOCK_DB_alice", "not_a_hash")
	_, err = checkPassword("alice", pw)
	if err == nil {
		fmt.Fprintln(os.Stderr, "Test 3 failed: expected error for invalid stored format")
		os.Exit(1)
	}

	// Test 4: Invalid userid type must raise error
	_, err = checkPassword(nil, pw)
	if err == nil {
		fmt.Fprintln(os.Stderr, "Test 4 failed: expected error for nil userid")
		os.Exit(1)
	}

	// Test 5: Invalid password type must raise error
	_, err = checkPassword("alice", nil)
	if err == nil {
		fmt.Fprintln(os.Stderr, "Test 5 failed: expected error for nil password")
		os.Exit(1)
	}

	// Test 6: Missing DB credentials must raise error
	os.Unsetenv("DB_USER")
	_, err = checkPassword("alice", pw)
	if err == nil {
		fmt.Fprintln(os.Stderr, "Test 6 failed: expected error for missing DB credentials")
		os.Exit(1)
	}

	fmt.Fprintln(os.Stdout, "All tests passed")
}