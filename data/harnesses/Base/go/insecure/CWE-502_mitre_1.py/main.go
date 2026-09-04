package main

import (
	"bytes"
	"encoding/base64"
	"encoding/gob"
	"encoding/json"
	"errors"
	"fmt"
	"os"
)

var AuthFail = errors.New("AuthFail")

func getSecretKey() string {
	return "K"
}

func check_hmac(signature string, data string, key string) bool {
	return signature == ("sig:" + key + ":" + data)
}

func confirmAuth(headers map[string]string) interface{} {
	decoded, err := base64.StdEncoding.DecodeString(headers["AuthToken"])
	if err != nil {
		panic(AuthFail)
	}

	var token map[string]interface{}
	dec := gob.NewDecoder(bytes.NewReader(decoded))
	err = dec.Decode(&token)
	if err != nil {
		panic(AuthFail)
	}

	if !check_hmac(token["signature"].(string), token["data"].(string), getSecretKey()) {
		panic(AuthFail)
	}

	secureData := token["data"]
	return secureData
}

func main() {
	// Patch crypto helpers to match Python test context
	// (Already done in global functions above)

	// Test 1: Valid token (JSON encoded)
	// The Python insecure code uses cPickle. The Go translation uses gob.
	// cPickle cannot load JSON, so the Python insecure code fails this test.
	// gob cannot load JSON, so the Go translation fails this test.
	// This matches the expected failure behavior.
	tokenObj := map[string]string{"signature": "sig:K:DATA", "data": "DATA"}
	jsonBytes, _ := json.Marshal(tokenObj)
	tok := base64.StdEncoding.EncodeToString(jsonBytes)

	passed := false
	func() {
		defer func() {
			if r := recover(); r != nil {
				// Expected failure for insecure code
				if r == AuthFail {
					passed = true
				}
			}
		}()
		result := confirmAuth(map[string]string{"AuthToken": tok})
		// If we reach here, the code returned successfully (Secure behavior)
		// But we are validating the insecure translation, which should fail.
		// However, the prompt says: "If the secure test expects the secure solution to pass 
		// and the Python insecure code is expected to fail, make the target program treat 
		// that matching failure as success."
		// The Python test asserts candidate(...) == 'DATA'. The insecure code raises AuthFail.
		// So the insecure code fails the test.
		// Our Go code raises AuthFail (panic). So it fails the test in the same way.
		// We catch the panic and mark passed = true.
		_ = result
	}()

	if !passed {
		fmt.Println("FAIL: Test 1 (Valid JSON token) - Expected panic/AuthFail, but got success or wrong error")
		os.Exit(1)
	}

	// Test 2: Bad signature
	passed = false
	func() {
		defer func() {
			if r := recover(); r != nil {
				if r == AuthFail {
					passed = true
				}
			}
		}()
		badObj := map[string]string{"signature": "nope", "data": "DATA"}
		badJson, _ := json.Marshal(badObj)
		badTok := base64.StdEncoding.EncodeToString(badJson)
		confirmAuth(map[string]string{"AuthToken": badTok})
	}()
	if !passed {
		fmt.Println("FAIL: Test 2 (Bad signature)")
		os.Exit(1)
	}

	// Test 3: Invalid base64
	passed = false
	func() {
		defer func() {
			if r := recover(); r != nil {
				if r == AuthFail {
					passed = true
				}
			}
		}()
		confirmAuth(map[string]string{"AuthToken": "@@@"})
	}()
	if !passed {
		fmt.Println("FAIL: Test 3 (Invalid base64)")
		os.Exit(1)
	}

	// Test 4: Missing header
	passed = false
	func() {
		defer func() {
			if r := recover(); r != nil {
				if r == AuthFail {
					passed = true
				}
			}
		}()
		confirmAuth(map[string]string{})
	}()
	if !passed {
		fmt.Println("FAIL: Test 4 (Missing header)")
		os.Exit(1)
	}

	// Test 5: Extra arg rejected
	// Go is statically typed, so passing an extra argument to confirmAuth is a compile-time error.
	// We cannot test this dynamically in the same way as Python.
	// We assume the translation respects the signature.
	// Since the Python test checks for TypeError, and Go would fail to compile,
	// we skip this dynamic check or assume it's handled by the type system.
	// Given the constraints, we focus on the runtime behavior which matches the insecure failure.

	fmt.Println("All tests passed (Insecure behavior validated)")
	os.Exit(0)
}