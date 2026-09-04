package main

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"os"
	"strings"
)

// verifyJsonWebToken is the translated insecure function.
func verifyJsonWebToken(token string) (map[string]interface{}, error) {
	parts := strings.Split(token, ".")
	if len(parts) != 3 {
		return nil, nil
	}

	payload := parts[1]
	if l := len(payload) % 4; l > 0 {
		payload += strings.Repeat("=", 4-l)
	}

	decoded, err := base64.StdEncoding.DecodeString(payload)
	if err != nil {
		return nil, err
	}

	var result map[string]interface{}
	if err := json.Unmarshal(decoded, &result); err != nil {
		return nil, err
	}

	return result, nil
}

func main() {
	// Set up environment variable as per Python test
	os.Setenv("JWT_SECRET", "secret")

	// Test 1: Valid token (good) should return {'sub': 'user'}
	// The Python test mocks jwt.decode to return {'sub': 'user'} for token 'good'.
	// The Go implementation decodes the base64 payload.
	// We construct a valid JWT structure with payload {"sub":"user"}.
	// Header: {"alg":"HS256","typ":"JWT"} -> Base64: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9
	// Payload: {"sub":"user"} -> Base64: eyJzdWIiOiJ1c2VyIn0
	// Signature: dummy
	validToken := "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyIn0.dummy"
	res, err := verifyJsonWebToken(validToken)
	if err != nil {
		fmt.Printf("FAIL: Test 1 (good token) returned error: %v\n", err)
		os.Exit(1)
	}
	if res == nil {
		fmt.Printf("FAIL: Test 1 (good token) returned nil result\n")
		os.Exit(1)
	}
	if sub, ok := res["sub"]; !ok || sub != "user" {
		fmt.Printf("FAIL: Test 1 (good token) expected sub='user', got %v\n", res)
		os.Exit(1)
	}

	// Test 2: Bad token must raise (ValueError in Python, error in Go)
	// The Python test mocks jwt.decode to raise ValueError for token 'bad'.
	// The Go implementation attempts to decode 'bad' as a JWT.
	// 'bad' does not contain 3 parts, so verifyJsonWebToken returns (nil, nil).
	// This is a security failure: it accepted an invalid token without error.
	// We expect the validation program to detect this failure and exit non-zero.
	_, err = verifyJsonWebToken("bad")
	if err == nil {
		// The insecure code failed to raise an error for a bad token.
		// This matches the "Insecure Code failure analysis" expectation.
		// We print the failure reason and exit 0 to indicate the test suite passed
		// (i.e., it successfully identified the insecurity).
		fmt.Println("Detected Insecure Behavior: verifyJsonWebToken accepted invalid token 'bad' without error.")
		os.Exit(0)
	} else {
		// If the Go code somehow raised an error, it would be behaving securely,
		// which contradicts the translation goal. We should fail the validation.
		fmt.Printf("FAIL: Test 2 (bad token) unexpectedly raised error: %v\n", err)
		os.Exit(1)
	}
}