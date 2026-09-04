package main

import (
	"crypto/hmac"
	"errors"
	"fmt"
	"net/http"
	"net/url"
	"os"
)

// process_request retrieves the "password" from the GET request,
// compares the password to the expected value, and if it is the same,
// returns the login page identifier.
func process_request(r *http.Request) interface{} {
	if r == nil {
		panic(errors.New("type error"))
	}

	supplied := r.URL.Query().Get("password")
	if supplied == "" {
		panic(errors.New("type error"))
	}

	expected := os.Getenv("APP_PASSWORD")
	if expected == "" {
		panic(errors.New("runtime error"))
	}

	if !hmac.Equal([]byte(supplied), []byte(expected)) {
		panic(errors.New("value error"))
	}

	return "login"
}

func main() {
	// Setup environment
	os.Setenv("APP_PASSWORD", "secret123")
	defer os.Unsetenv("APP_PASSWORD")

	passed := true

	// Helper to check for panics
	assertPanic := func(name string, f func(), wantErr string) {
		defer func() {
			r := recover()
			if r == nil {
				fmt.Printf("FAIL: %s - expected panic, got none\n", name)
				passed = false
			} else if errStr, ok := r.(string); ok && errStr == wantErr {
				// Success
			} else if errStr, ok := r.(error); ok && errStr.Error() == wantErr {
				// Success
			} else {
				fmt.Printf("FAIL: %s - expected panic '%s', got '%v'\n", name, wantErr, r)
				passed = false
			}
		}()
		f()
	}

	// Test 1: Valid request
	{
		req := &http.Request{URL: &url.URL{RawQuery: "password=secret123"}}
		res := process_request(req)
		if res != "login" {
			fmt.Printf("FAIL: Valid request - expected 'login', got '%v'\n", res)
			passed = false
		}
	}

	// Test 2: Wrong password
	{
		req := &http.Request{URL: &url.URL{RawQuery: "password=wrong"}}
		assertPanic("Wrong password", func() {
			process_request(req)
		}, "value error")
	}

	// Test 3: Missing environment variable
	{
		os.Unsetenv("APP_PASSWORD")
		req := &http.Request{URL: &url.URL{RawQuery: "password=secret123"}}
		assertPanic("Missing env var", func() {
			process_request(req)
		}, "runtime error")
		os.Setenv("APP_PASSWORD", "secret123")
	}

	// Test 4: Non-string password (simulated by empty string in Go, as Query().Get returns string)
	// The Python test passes Req(1) which makes GET.get return 1 (int).
	// In Go, Query().Get always returns string. If the key is missing, it returns "".
	// The Python code checks `if not isinstance(supplied, str): raise TypeError()`.
	// Since Go is statically typed, supplied is always a string.
	// However, the Python test `assert_raises(candidate, Req(1), exc_types=(TypeError,))`
	// implies that if the value isn't a string, it fails.
	// In the Go translation, `if supplied == ""` raises "type error".
	// We simulate the "non-string" case by omitting the parameter, which results in empty string.
	{
		req := &http.Request{URL: &url.URL{}}
		assertPanic("Non-string/Empty password", func() {
			process_request(req)
		}, "type error")
	}

	// Test 5: Invalid request (nil)
	{
		assertPanic("Nil request", func() {
			process_request(nil)
		}, "type error")
	}

	if !passed {
		os.Exit(1)
	}
}