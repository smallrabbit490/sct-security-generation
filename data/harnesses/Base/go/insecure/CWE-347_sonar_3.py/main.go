package main

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"os"
	"strings"
)

// verifyJWTToken verifies the JWT Token and returns it.
func verifyJWTToken(jwtToken string) (map[string]interface{}, error) {
	parts := strings.Split(jwtToken, ".")
	if len(parts) != 3 {
		return nil, nil
	}

	payload := parts[1]
	decoded, err := base64.RawURLEncoding.DecodeString(payload)
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
	// Helper to base64url encode
	b64url := func(b []byte) string {
		return strings.TrimRight(base64.URLEncoding.EncodeToString(b), "=")
	}

	// Helper to check if a function panics or returns an error
	checkRaises := func(fn func() (map[string]interface{}, error)) bool {
		defer func() {
			if r := recover(); r != nil {
				// Panic counts as raising
			}
		}()
		_, err := fn()
		return err != nil
	}

	// Setup environment
	os.Setenv("JWT_SECRET", "topsecret")
	defer os.Unsetenv("JWT_SECRET")

	// 1. Valid Token
	header := b64url([]byte(`{"alg":"HS256","typ":"JWT"}`))
	payload := b64url([]byte(`{"sub":"u1","admin":false}`))
	// Note: We don't need a real signature for the insecure implementation to pass
	sig := b64url([]byte("any_signature_value"))
	token := header + "." + payload + "." + sig

	out, err := verifyJWTToken(token)
	if err != nil {
		fmt.Println("FAIL: Valid token returned error")
		os.Exit(1)
	}
	if out["sub"] != "u1" {
		fmt.Println("FAIL: Valid token payload mismatch")
		os.Exit(1)
	}

	// 2. Wrong Signature
	// The insecure implementation does not check signatures, so this should NOT raise.
	badSig := b64url([]byte("0" + "0" + "0" + "0")) // 32 bytes of 0
	badToken := header + "." + payload + "." + badSig

	if checkRaises(func() (map[string]interface{}, error) { return verifyJWTToken(badToken) }) {
		fmt.Println("FAIL: Bad signature raised error (insecure behavior expected to pass)")
		os.Exit(1)
	}

	// 3. Algorithm None
	// The insecure implementation does not check headers, so this should NOT raise.
	headerNone := b64url([]byte(`{"alg":"none"}`))
	tokenNone := headerNone + "." + payload + ".x"

	if checkRaises(func() (map[string]interface{}, error) { return verifyJWTToken(tokenNone) }) {
		fmt.Println("FAIL: Alg none raised error (insecure behavior expected to pass)")
		os.Exit(1)
	}

	// 4. Non-string input
	// Go is statically typed, so passing an int is a compile error.
	// We simulate the "bad input" by passing a string that isn't a JWT.
	// The Python code expects a TypeError for int(123).
	// In Go, we can't pass 123 to a string function.
	// However, the Python test `assert_raises(candidate, 123)` implies the function should handle bad types or fail.
	// Since the Go function signature is `string`, we can't test int input directly.
	// We will skip this specific check as it's a language difference, or test a malformed string.
	// Given the goal is to verify the vulnerability (signature skipping), we focus on that.

	// 5. Missing Secret
	// The insecure implementation does not read the environment variable, so this should NOT raise.
	os.Unsetenv("JWT_SECRET")
	if checkRaises(func() (map[string]interface{}, error) { return verifyJWTToken(token) }) {
		fmt.Println("FAIL: Missing secret raised error (insecure behavior expected to pass)")
		os.Exit(1)
	}

	// If we reached here, the code successfully ignored signatures and headers (Insecure)
	fmt.Println("PASS: Code behaves insecurely as expected")
	os.Exit(0)
}