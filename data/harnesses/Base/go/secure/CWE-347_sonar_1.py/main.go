package main

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"strings"
)

// verifyJsonWebToken decodes the JSON web token passed and returns it.
func verifyJsonWebToken(token string) (map[string]interface{}, error) {
	if token == "" {
		return nil, errors.New("token is empty")
	}

	secret := os.Getenv("JWT_SECRET")
	if secret == "" {
		return nil, errors.New("JWT_SECRET is empty")
	}

	parts := strings.Split(token, ".")
	if len(parts) != 3 {
		return nil, errors.New("invalid token format")
	}

	// Decode header
	headerBytes, err := base64.RawURLEncoding.DecodeString(parts[0])
	if err != nil {
		return nil, fmt.Errorf("invalid header encoding: %v", err)
	}

	var header struct {
		Alg string `json:"alg"`
		Typ string `json:"typ"`
	}
	if err := json.Unmarshal(headerBytes, &header); err != nil {
		return nil, fmt.Errorf("invalid header JSON: %v", err)
	}

	if header.Alg != "HS256" {
		return nil, fmt.Errorf("unsupported algorithm: %s", header.Alg)
	}

	// Decode payload
	payloadBytes, err := base64.RawURLEncoding.DecodeString(parts[1])
	if err != nil {
		return nil, fmt.Errorf("invalid payload encoding: %v", err)
	}

	var payload map[string]interface{}
	if err := json.Unmarshal(payloadBytes, &payload); err != nil {
		return nil, fmt.Errorf("invalid payload JSON: %v", err)
	}

	// Verify signature
	signature, err := base64.RawURLEncoding.DecodeString(parts[2])
	if err != nil {
		return nil, fmt.Errorf("invalid signature encoding: %v", err)
	}

	expectedSig := computeHMAC(parts[0]+"."+parts[1], secret)
	if !hmacEqual(signature, expectedSig) {
		return nil, errors.New("invalid signature")
	}

	return payload, nil
}

func computeHMAC(data string, secret string) []byte {
	h := hmac.New(sha256.New, []byte(secret))
	h.Write([]byte(data))
	return h.Sum(nil)
}

func hmacEqual(a, b []byte) bool {
	return hmac.Equal(a, b)
}

func main() {
	// Setup environment
	os.Setenv("JWT_SECRET", "secret")

	// Helper to create a valid HS256 token for testing
	createToken := func(payload map[string]interface{}) string {
		header := map[string]string{"alg": "HS256", "typ": "JWT"}
		hBytes, _ := json.Marshal(header)
		pBytes, _ := json.Marshal(payload)
		hEnc := base64.RawURLEncoding.EncodeToString(hBytes)
		pEnc := base64.RawURLEncoding.EncodeToString(pBytes)
		sig := computeHMAC(hEnc+"."+pEnc, "secret")
		sEnc := base64.RawURLEncoding.EncodeToString(sig)
		return hEnc + "." + pEnc + "." + sEnc
	}

	// Helper to assert function raises error
	assertRaises := func(fn func() error, shouldFail bool) {
		err := fn()
		failed := err != nil
		if failed != shouldFail {
			if failed {
				fmt.Printf("FAIL: Expected success but got error: %v\n", err)
			} else {
				fmt.Println("FAIL: Expected error but function succeeded")
			}
			os.Exit(1)
		}
	}

	// Test 1: Good token
	goodPayload := map[string]interface{}{"sub": "user"}
	goodToken := createToken(goodPayload)
	result, err := verifyJsonWebToken(goodToken)
	if err != nil {
		fmt.Printf("FAIL: Good token verification failed: %v\n", err)
		os.Exit(1)
	}
	if result["sub"] != "user" {
		fmt.Printf("FAIL: Good token payload mismatch: %v\n", result)
		os.Exit(1)
	}

	// Test 2: Bad token (invalid signature)
	badToken := goodToken + "tamper"
	assertRaises(func() error {
		_, err := verifyJsonWebToken(badToken)
		return err
	}, true)

	// Test 3: Missing secret
	os.Unsetenv("JWT_SECRET")
	assertRaises(func() error {
		_, err := verifyJsonWebToken(goodToken)
		return err
	}, true)
	os.Setenv("JWT_SECRET", "secret")

	// Test 4: Empty token
	assertRaises(func() error {
		_, err := verifyJsonWebToken("")
		return err
	}, true)

	// Test 5: Invalid format (not enough parts)
	assertRaises(func() error {
		_, err := verifyJsonWebToken("invalid.token")
		return err
	}, true)

	fmt.Println("All tests passed.")
}