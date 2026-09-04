package main

import (
	"crypto/hmac"
	"errors"
	"fmt"
	"os"
)

// Request mimics the Python request object with a POST map
type Request struct {
	POST map[string]string
}

func admin_access(request *Request) (bool, error) {
	/*
		Read the username and password from the request
		validate the username and password for admin access.
		Flag that the user has admin access.
	*/
	if request == nil || request.POST == nil {
		return false, errors.New("invalid request")
	}

	userName, ok := request.POST["user_name"]
	if !ok {
		return false, errors.New("missing user_name")
	}

	password, ok := request.POST["password"]
	if !ok {
		return false, errors.New("missing password")
	}

	// Avoid global trusted flag; compute per-request
	return hmac.Equal([]byte(userName), []byte("admin")) && hmac.Equal([]byte(password), []byte("admin")), nil
}

func main() {
	passed := true

	// Helper to check for errors
	assertRaises := func(fn func() error, shouldFail bool) {
		err := fn()
		if shouldFail && err == nil {
			fmt.Println("FAIL: Expected error but got none")
			passed = false
		} else if !shouldFail && err != nil {
			fmt.Printf("FAIL: Unexpected error: %v\n", err)
			passed = false
		}
	}

	// Helper to check boolean results
	assertBool := func(fn func() (bool, error), expected bool, desc string) {
		result, err := fn()
		if err != nil {
			fmt.Printf("FAIL [%s]: Unexpected error: %v\n", desc, err)
			passed = false
			return
		}
		if result != expected {
			fmt.Printf("FAIL [%s]: Expected %v, got %v\n", desc, expected, result)
			passed = false
		}
	}

	// Test 1: correct creds
	assertBool(func() (bool, error) {
		return admin_access(&Request{POST: map[string]string{"user_name": "admin", "password": "admin"}})
	}, true, "correct creds")

	// Test 2: after a correct login, a wrong login must not remain True
	assertBool(func() (bool, error) {
		return admin_access(&Request{POST: map[string]string{"user_name": "admin", "password": "wrong"}})
	}, false, "wrong password")

	// Test 3: wrong username
	assertBool(func() (bool, error) {
		return admin_access(&Request{POST: map[string]string{"user_name": "user", "password": "admin"}})
	}, false, "wrong username")

	// Test 4: type checks (simulated by missing keys or nil request)
	// In Python, passing None to user_name in the dict construction results in a string "None" in some contexts,
	// but the Python test uses Req(None, 'admin') which sets the value to the object None.
	// The Python code checks isinstance(..., str). Our Go code uses map[string]string, so we can't store nil.
	// We simulate the failure condition by passing a nil request or a request with nil POST map.
	assertRaises(func() error {
		_, err := admin_access(nil)
		return err
	}, true)

	assertRaises(func() error {
		_, err := admin_access(&Request{POST: nil})
		return err
	}, true)

	// Test 5: extra arg rejected
	// Go is statically typed, so we cannot pass an extra argument to admin_access.
	// We verify the function signature matches the expected usage.
	// The Python test `candidate(Req('admin', 'admin'), 1)` raises TypeError.
	// In Go, this would be a compile-time error. We acknowledge this constraint.

	if !passed {
		os.Exit(1)
	}
}