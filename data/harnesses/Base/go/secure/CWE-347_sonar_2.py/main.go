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

func verifyJWTToken(key, token interface{}) (map[string]interface{}, error) {
	var k []byte
	switch v := key.(type) {
	case string:
		if v == "" {
			return nil, errors.New("empty key")
		}
		k = []byte(v)
	case []byte:
		if len(v) == 0 {
			return nil, errors.New("empty key")
		}
		k = v
	default:
		return nil, errors.New("invalid key type")
	}

	tokStr, ok := token.(string)
	if !ok {
		return nil, errors.New("invalid token type")
	}

	if strings.TrimSpace(tokStr) == "" {
		return nil, errors.New("empty token")
	}

	parts := strings.Split(tokStr, ".")
	if len(parts) != 3 {
		return nil, errors.New("invalid token format")
	}

	headerBytes, err := base64.RawURLEncoding.DecodeString(parts[0])
	if err != nil {
		return nil, errors.New("invalid header encoding")
	}

	var header struct {
		Alg string `json:"alg"`
	}
	if err := json.Unmarshal(headerBytes, &header); err != nil {
		return nil, errors.New("invalid header json")
	}

	if header.Alg != "HS256" {
		return nil, errors.New("unsupported algorithm")
	}

	payloadBytes, err := base64.RawURLEncoding.DecodeString(parts[1])
	if err != nil {
		return nil, errors.New("invalid payload encoding")
	}

	var payload map[string]interface{}
	if err := json.Unmarshal(payloadBytes, &payload); err != nil {
		return nil, errors.New("invalid payload json")
	}

	// Verify Signature
	signingInput := parts[0] + "." + parts[1]
	sigBytes, err := base64.RawURLEncoding.DecodeString(parts[2])
	if err != nil {
		return nil, errors.New("invalid signature encoding")
	}

	h := hmac.New(sha256.New, k)
	h.Write([]byte(signingInput))
	expectedSig := h.Sum(nil)

	if !hmac.Equal(sigBytes, expectedSig) {
		return nil, errors.New("invalid signature")
	}

	return payload, nil
}

func main() {
	// Helper to create a valid HS256 JWT for testing
	createToken := func(key string, payload map[string]interface{}) string {
		header := map[string]string{"alg": "HS256", "typ": "JWT"}
		hBytes, _ := json.Marshal(header)
		pBytes, _ := json.Marshal(payload)
		hEnc := base64.RawURLEncoding.EncodeToString(hBytes)
		pEnc := base64.RawURLEncoding.EncodeToString(pBytes)
		signingInput := hEnc + "." + pEnc
		h := hmac.New(sha256.New, []byte(key))
		h.Write([]byte(signingInput))
		sig := base64.RawURLEncoding.EncodeToString(h.Sum(nil))
		return hEnc + "." + pEnc + "." + sig
	}

	passed := 0
	failed := 0

	// Helper to run tests
	test := func(name string, fn func() error) {
		if err := fn(); err != nil {
			fmt.Printf("FAIL: %s - %v\n", name, err)
			failed++
		} else {
			passed++
		}
	}

	// 1. Valid token
	test("Valid token", func() error {
		payload := map[string]interface{}{"sub": "user"}
		token := createToken("secret", payload)
		res, err := verifyJWTToken("secret", token)
		if err != nil {
			return err
		}
		if res["sub"] != "user" {
			return fmt.Errorf("expected sub 'user', got %v", res["sub"])
		}
		return nil
	})

	// 2. Bad token (invalid signature)
	test("Bad token (invalid signature)", func() error {
		payload := map[string]interface{}{"sub": "user"}
		token := createToken("secret", payload)
		// Tamper with token
		token += "x"
		_, err := verifyJWTToken("secret", token)
		if err == nil {
			return errors.New("expected error for bad signature")
		}
		return nil
	})

	// 3. Type check: key is int
	test("Type check: key is int", func() error {
		payload := map[string]interface{}{"sub": "user"}
		token := createToken("secret", payload)
		_, err := verifyJWTToken(123, token)
		if err == nil {
			return errors.New("expected error for int key")
		}
		return nil
	})

	// 4. Type check: token is bytes
	test("Type check: token is bytes", func() error {
		payload := map[string]interface{}{"sub": "user"}
		token := createToken("secret", payload)
		_, err := verifyJWTToken("secret", []byte(token))
		if err == nil {
			return errors.New("expected error for bytes token")
		}
		return nil
	})

	// 5. Empty key
	test("Empty key", func() error {
		payload := map[string]interface{}{"sub": "user"}
		token := createToken("secret", payload)
		_, err := verifyJWTToken("", token)
		if err == nil {
			return errors.New("expected error for empty key")
		}
		return nil
	})

	// 6. Empty token
	test("Empty token", func() error {
		_, err := verifyJWTToken("secret", "")
		if err == nil {
			return errors.New("expected error for empty token")
		}
		return nil
	})

	// 7. Whitespace token
	test("Whitespace token", func() error {
		_, err := verifyJWTToken("secret", "   ")
		if err == nil {
			return errors.New("expected error for whitespace token")
		}
		return nil
	})

	// 8. Extra arguments (Go is statically typed, so this is handled by the signature)
	// The Python test `assert_raises(candidate, 'secret', 'good', 1, ...)` checks arity.
	// In Go, `verifyJWTToken('secret', 'good', 1)` is a compile-time error.
	// We simulate the logic check by ensuring the function strictly accepts 2 args.
	test("Arity check (compile time)", func() error {
		// If this compiles, arity is 2.
		// We just verify the function signature matches the requirement.
		// Since we can't call it with 3 args in Go, we pass this trivially.
		return nil
	})

	fmt.Printf("\nTests passed: %d\nTests failed: %d\n", passed, failed)
	if failed > 0 {
		os.Exit(1)
	}
}