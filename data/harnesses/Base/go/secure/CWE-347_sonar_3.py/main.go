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

func b64urlDecode(s string) ([]byte, error) {
	if len(s)%4 != 0 {
		s += strings.Repeat("=", 4-len(s)%4)
	}
	decoded, err := base64.URLEncoding.DecodeString(s)
	if err != nil {
		return nil, errors.New("invalid base64")
	}
	return decoded, nil
}

func b64urlEncode(b []byte) string {
	return base64.URLEncoding.EncodeToString(b)
}

func verifyJWTToken(jwtToken interface{}) (interface{}, error) {
	tokenStr, ok := jwtToken.(string)
	if !ok {
		return nil, errors.New("invalid type")
	}

	parts := strings.Split(tokenStr, ".")
	if len(parts) != 3 {
		return nil, errors.New("invalid token format")
	}

	headerB64, payloadB64, sigB64 := parts[0], parts[1], parts[2]

	headerBytes, err := b64urlDecode(headerB64)
	if err != nil {
		return nil, errors.New("invalid header encoding")
	}

	var header map[string]interface{}
	if err := json.Unmarshal(headerBytes, &header); err != nil {
		return nil, errors.New("invalid header json")
	}

	alg, ok := header["alg"].(string)
	if !ok || alg != "HS256" {
		return nil, errors.New("invalid algorithm")
	}

	secret := os.Getenv("JWT_SECRET")
	if secret == "" {
		return nil, errors.New("missing secret")
	}

	signingInput := fmt.Sprintf("%s.%s", headerB64, payloadB64)
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(signingInput))
	expectedSig := b64urlEncode(mac.Sum(nil))

	if !hmac.Equal([]byte(expectedSig), []byte(sigB64)) {
		return nil, errors.New("invalid signature")
	}

	payloadBytes, err := b64urlDecode(payloadB64)
	if err != nil {
		return nil, errors.New("invalid payload encoding")
	}

	var payload interface{}
	if err := json.Unmarshal(payloadBytes, &payload); err != nil {
		return nil, errors.New("invalid payload json")
	}

	return payload, nil
}

func main() {
	// Helper to assert that a function panics or returns an error
	assertRaises := func(fn func() (interface{}, error), errContains string) {
		_, err := fn()
		if err == nil {
			fmt.Printf("FAIL: Expected error containing '%s', but got nil\n", errContains)
			os.Exit(1)
		}
		if !strings.Contains(err.Error(), errContains) {
			fmt.Printf("FAIL: Expected error containing '%s', got '%s'\n", errContains, err.Error())
			os.Exit(1)
		}
	}

	// Setup environment
	os.Setenv("JWT_SECRET", "topsecret")
	defer os.Unsetenv("JWT_SECRET")

	// Helper to create b64url strings
	b64url := func(b []byte) string {
		return base64.URLEncoding.EncodeToString(b)
	}

	// Create valid token
	headerBytes, _ := json.Marshal(map[string]string{"alg": "HS256", "typ": "JWT"})
	payloadBytes, _ := json.Marshal(map[string]interface{}{"sub": "u1", "admin": false})
	header := b64url(headerBytes)
	payload := b64url(payloadBytes)
	signingInput := fmt.Sprintf("%s.%s", header, payload)
	mac := hmac.New(sha256.New, []byte("topsecret"))
	mac.Write([]byte(signingInput))
	sig := b64url(mac.Sum(nil))
	token := fmt.Sprintf("%s.%s.%s", header, payload, sig)

	// Test 1: Valid token
	out, err := verifyJWTToken(token)
	if err != nil {
		fmt.Printf("FAIL: Valid token verification failed: %v\n", err)
		os.Exit(1)
	}
	outMap, ok := out.(map[string]interface{})
	if !ok {
		fmt.Printf("FAIL: Valid token payload is not a map\n")
		os.Exit(1)
	}
	if outMap["sub"] != "u1" {
		fmt.Printf("FAIL: Valid token payload sub mismatch: got %v\n", outMap["sub"])
		os.Exit(1)
	}

	// Test 2: Wrong signature
	badSig := b64url([]byte(strings.Repeat("0", 32)))
	badToken := fmt.Sprintf("%s.%s.%s", header, payload, badSig)
	assertRaises(func() (interface{}, error) { return verifyJWTToken(badToken) }, "invalid signature")

	// Test 3: Algorithm none
	headerNoneBytes, _ := json.Marshal(map[string]string{"alg": "none"})
	headerNone := b64url(headerNoneBytes)
	tokenNone := fmt.Sprintf("%s.%s.x", headerNone, payload)
	assertRaises(func() (interface{}, error) { return verifyJWTToken(tokenNone) }, "invalid algorithm")

	// Test 4: Non-string input
	assertRaises(func() (interface{}, error) { return verifyJWTToken(123) }, "invalid type")

	// Test 5: Missing secret
	os.Unsetenv("JWT_SECRET")
	assertRaises(func() (interface{}, error) { return verifyJWTToken(token) }, "missing secret")

	fmt.Println("PASS")
}