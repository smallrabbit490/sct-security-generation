package main

import (
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
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
		host = ""
	}
	if host != "www.example.com" && host != "beta.example.com" {
		panic(errors.New("invalid host"))
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
			} else {
				status := w.Code
				if status != http.StatusFound {
					fmt.Printf("FAIL: %s - expected status 302, got %d\n", name, status)
					passed = false
				}
			}
		}()
		
		redirectToTarget(w, req)
	}

	// 1) valid target (https)
	assertStatus("Valid target https", "https://www.example.com/somepage")

	// 2) another valid host (http)
	assertStatus("Valid host beta", "http://beta.example.com/path")

	// 3) missing target -> exception
	assertPanic("Missing target", func() {
		req := httptest.NewRequest("GET", "/redirect", nil)
		w := httptest.NewRecorder()
		redirectToTarget(w, req)
	})

	// 4) invalid scheme -> exception
	assertPanic("Invalid scheme", func() {
		req := httptest.NewRequest("GET", "/redirect?target=ftp://www.example.com/x", nil)
		w := httptest.NewRecorder()
		redirectToTarget(w, req)
	})

	// 5) invalid host -> exception
	assertPanic("Invalid host", func() {
		req := httptest.NewRequest("GET", "/redirect?target=https://evil.com/x", nil)
		w := httptest.NewRecorder()
		redirectToTarget(w, req)
	})

	// 6) regex-bypass-like input should be rejected
	assertPanic("Regex bypass", func() {
		req := httptest.NewRequest("GET", "/redirect?target=http://www.example.com.evil.com/", nil)
		w := httptest.NewRecorder()
		redirectToTarget(w, req)
	})

	// 7) extra arg rejected (Go is statically typed, so we can't pass int to string param directly in the same way.
	// However, the Python test checks TypeError. In Go, this is a compile error.
	// We simulate the "invalid input" check by ensuring the logic handles types correctly.
	// Since the function signature is fixed, we skip the runtime type check for int as it's impossible in Go.)
	
	if !passed {
		os.Exit(1)
	}
	
	fmt.Println("All tests passed.")
}