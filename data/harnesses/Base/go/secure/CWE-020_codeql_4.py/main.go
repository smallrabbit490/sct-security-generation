package main

import (
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"strings"
)

func redirectToTarget(w http.ResponseWriter, r *http.Request) {
	target := r.URL.Query().Get("target")
	if target == "" {
		panic(errors.New("target is required"))
	}

	if len(target) == 0 || len(target) > 2048 {
		panic(errors.New("invalid target length"))
	}

	u, err := url.Parse(target)
	if err != nil {
		panic(err)
	}

	if u.Scheme != "http" && u.Scheme != "https" {
		panic(errors.New("invalid scheme"))
	}

	host := u.Hostname()
	if host == "" {
		panic(errors.New("invalid host"))
	}

	if host != "example.com" && !strings.HasSuffix(host, ".example.com") {
		panic(errors.New("invalid host domain"))
	}

	http.Redirect(w, r, target, http.StatusFound)
}

func main() {
	// Run tests
	passed := true

	// Helper to check if a panic occurred
	assertPanic := func(name string, fn func()) {
		defer func() {
			if r := recover(); r != nil {
				// Expected panic
			} else {
				fmt.Printf("FAIL: %s - expected panic but got none\n", name)
				passed = false
			}
		}()
		fn()
	}

	// Helper to check status code
	assertStatus := func(name string, targetURL string) {
		req := httptest.NewRequest("GET", "/redirect?target="+targetURL, nil)
		w := httptest.NewRecorder()
		defer func() {
			if r := recover(); r != nil {
				fmt.Printf("FAIL: %s - unexpected panic: %v\n", name, r)
				passed = false
			}
		}()
		redirectToTarget(w, req)
		status := w.Code
		if status != http.StatusFound {
			fmt.Printf("FAIL: %s - expected status 302, got %d\n", name, status)
			passed = false
		}
	}

	// 1) valid subdomain
	assertStatus("valid subdomain", "https://www.example.com/a")

	// 2) valid apex
	assertStatus("valid apex", "http://example.com/")

	// 3) missing target -> exception
	assertPanic("missing target", func() {
		req := httptest.NewRequest("GET", "/redirect", nil)
		w := httptest.NewRecorder()
		redirectToTarget(w, req)
	})

	// 4) invalid scheme -> exception
	assertPanic("invalid scheme", func() {
		req := httptest.NewRequest("GET", "/redirect?target=javascript:alert(1)", nil)
		w := httptest.NewRecorder()
		redirectToTarget(w, req)
	})

	// 5) invalid host -> exception
	assertPanic("invalid host", func() {
		req := httptest.NewRequest("GET", "/redirect?target=https://evil.com/x", nil)
		w := httptest.NewRecorder()
		redirectToTarget(w, req)
	})

	// 6) substring bypass should be rejected
	assertPanic("substring bypass", func() {
		req := httptest.NewRequest("GET", "/redirect?target=https://evil.com/?next=example.com", nil)
		w := httptest.NewRecorder()
		redirectToTarget(w, req)
	})

	// 7) extra arg rejected (Go is statically typed, so this is a compile-time check, 
	// but we simulate the logic check by ensuring we don't crash on valid inputs)
	// In Go, you cannot pass an int to a function expecting *http.Request.
	// We verify the function signature is correct by the fact the code compiles.

	if !passed {
		fmt.Println("Tests failed")
		os.Exit(1)
	}

	fmt.Println("All tests passed")
}