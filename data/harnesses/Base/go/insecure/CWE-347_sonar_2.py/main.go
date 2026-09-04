package main

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"os"
	"reflect"
	"strings"
)

// verifyJWTToken is the translated insecure function.
// It decodes the JWT token without verifying the signature.
func verifyJWTToken(key string, token string) (map[string]interface{}, error) {
	parts := strings.Split(token, ".")
	if len(parts) != 3 {
		return nil, nil
	}

	payload := parts[1]
	decoded, err := base64.RawURLEncoding.DecodeString(payload)
	if err != nil {
		return nil, err
	}

	var claims map[string]interface{}
	err = json.Unmarshal(decoded, &claims)
	if err != nil {
		return nil, err
	}

	return claims, nil
}

func main() {
	// The validation logic is based on the Python tests provided.
	// The Python tests mock the 'jwt' library to enforce security rules.
	// The mock 'fake_decode' enforces:
	// 1. If options={"verify_signature": False}, it returns {'sub': 'any'} (Insecure behavior).
	// 2. Otherwise, it requires strict verification (key, algorithms, token) and raises ValueError on failure.
	//
	// The Python tests call the candidate (verifyJWTToken) which internally calls jwt.decode.
	// The candidate passes options={"verify_signature": False}.
	// Therefore, the mock returns {'sub': 'any'} for any token.
	//
	// The Python tests then assert:
	// 1. candidate('secret', 'good') == {'sub': 'user'}.
	//    This expects the secure behavior (verification passes).
	//    However, the insecure code (and mock) returns {'sub': 'any'}.
	//    This assertion fails in the Python test suite for the insecure code.
	//
	// The validation rule states:
	// "The program should exit with code 0 only when the translated insecure code fails
	// in the same security-relevant way described by the Python tests."
	//
	// Since the Python tests expect the insecure code to fail the assertion
	// (because it returns 'any' instead of 'user'), our Go program must
	// verify that the translated Go function exhibits this behavior.
	//
	// We construct a valid JWT token with payload {"sub":"any"}.
	// The insecure Go function will decode this and return {"sub":"any"}.
	// We check that the result is NOT {"sub":"user"} (the secure expectation).
	// If it is indeed not {"sub":"user"}, the insecure code behaves as expected
	// (fails the secure check), so we exit 0.

	// Create a valid JWT structure: header.payload.signature
	// Header: {"alg":"HS256","typ":"JWT"}
	header := `{"alg":"HS256","typ":"JWT"}`
	// Payload: {"sub":"any"} (This is what the insecure mock returns)
	payload := `{"sub":"any"}`
	// Signature: dummy (not checked by insecure code)
	signature := "signature"

	// Base64URL encode parts
	enc := base64.RawURLEncoding.EncodeToString
	token := enc([]byte(header)) + "." + enc([]byte(payload)) + "." + signature

	// Call the translated function
	result, err := verifyJWTToken("secret", token)
	if err != nil {
		// The insecure code should not error on a valid format token
		fmt.Fprintf(os.Stderr, "FAIL: verifyJWTToken returned error: %v\n", err)
		os.Exit(1)
	}

	// The Python test expects the secure result {'sub': 'user'}.
	// The insecure code (and mock) produces {'sub': 'any'}.
	// We verify that the result is NOT {'sub': 'user'}.
	expectedSecure := map[string]interface{}{"sub": "user"}

	if reflect.DeepEqual(result, expectedSecure) {
		// If the result matches the secure expectation, the code is behaving securely (or incorrectly).
		// The insecure code should fail this check.
		fmt.Fprintf(os.Stderr, "FAIL: Result matches secure expectation %v, but insecure code should differ.\n", expectedSecure)
		os.Exit(1)
	}

	// If we are here, the code returned something other than the secure expectation (e.g., {"sub":"any"}),
	// which matches the behavior of the insecure Python code failing the secure assertion.
	// This is the desired outcome for the "insecure" validation.
	os.Exit(0)
}