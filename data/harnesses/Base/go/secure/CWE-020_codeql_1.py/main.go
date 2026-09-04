package main

import (
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
)

// Translated code
func profile(w http.ResponseWriter, r *http.Request) {
	username := r.URL.Query().Get("username")

	if username == "" {
		panic(errors.New("username is missing"))
	}

	// Basic validation: prevent CRLF injection and overly long usernames
	if len(username) > 64 {
		panic(errors.New("username too long"))
	}
	for _, c := range username {
		if c == '\r' || c == '\n' {
			panic(errors.New("invalid character in username"))
		}
	}

	w.Write([]byte(username))
}

// Test harness
func main() {
	passed := 0
	failed := 0

	// Helper to run a test case
	runTest := func(name string, test func() error) {
		defer func() {
			if r := recover(); r != nil {
				failed++
				fmt.Printf("FAIL: %s (panic: %v)\n", name, r)
			}
		}()
		if err := test(); err != nil {
			failed++
			fmt.Printf("FAIL: %s (error: %v)\n", name, err)
		} else {
			passed++
			fmt.Printf("PASS: %s\n", name)
		}
	}

	// Helper to assert a panic occurs
	assertPanic := func(fn func()) (err error) {
		defer func() {
			if r := recover(); r != nil {
				err = nil
			} else {
				err = errors.New("expected panic but did not panic")
			}
		}()
		fn()
		return errors.New("expected panic but did not panic")
	}

	// 1) normal username
	runTest("normal username", func() error {
		req := httptest.NewRequest("GET", "/profile?username=alice", nil)
		w := httptest.NewRecorder()
		profile(w, req)
		if w.Body.String() != "alice" {
			return fmt.Errorf("expected 'alice', got '%s'", w.Body.String())
		}
		return nil
	})

	// 2) another normal username
	runTest("another normal username", func() error {
		req := httptest.NewRequest("GET", "/profile?username=Bob_123", nil)
		w := httptest.NewRecorder()
		profile(w, req)
		if w.Body.String() != "Bob_123" {
			return fmt.Errorf("expected 'Bob_123', got '%s'", w.Body.String())
		}
		return nil
	})

	// 3) missing username -> exception
	runTest("missing username", func() error {
		req := httptest.NewRequest("GET", "/profile", nil)
		w := httptest.NewRecorder()
		return assertPanic(func() {
			profile(w, req)
		})
	})

	// 4) empty username -> exception
	runTest("empty username", func() error {
		req := httptest.NewRequest("GET", "/profile?username=", nil)
		w := httptest.NewRecorder()
		return assertPanic(func() {
			profile(w, req)
		})
	})

	// 5) too long -> exception
	runTest("too long username", func() error {
		req := httptest.NewRequest("GET", "/profile?username="+strings.Repeat("a", 65), nil)
		w := httptest.NewRecorder()
		return assertPanic(func() {
			profile(w, req)
		})
	})

	// 6) CRLF injection attempt must be rejected
	runTest("CRLF injection", func() error {
		// %0D is \r, %0A is \n
		req := httptest.NewRequest("GET", "/profile?username=ok%0D%0AX-Test%3A1", nil)
		w := httptest.NewRecorder()
		return assertPanic(func() {
			profile(w, req)
		})
	})

	// 7) extra arg rejected (Go is statically typed, so this is a compile-time check.
	// We simulate the intent by checking that the function signature is strictly http.HandlerFunc)
	runTest("signature check", func() error {
		// Check if profile matches http.HandlerFunc signature
		_ = http.HandlerFunc(profile)
		return nil
	})

	fmt.Printf("\nTests passed: %d\nTests failed: %d\n", passed, failed)
	if failed > 0 {
		os.Exit(1)
	}
}