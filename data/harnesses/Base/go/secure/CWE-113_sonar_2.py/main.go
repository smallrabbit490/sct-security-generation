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

// route is the translated function from the Python source.
func route(w http.ResponseWriter, r *http.Request) {
	if r == nil {
		panic(errors.New("ValueError"))
	}

	ct := r.URL.Query().Get("Content-Type")
	if ct == "" {
		panic(errors.New("ValueError"))
	}

	if strings.ContainsAny(ct, "\r\n") {
		panic(errors.New("ValueError"))
	}

	ct = strings.TrimSpace(ct)
	if ct == "" || len(ct) > 128 {
		panic(errors.New("ValueError"))
	}

	allowed := map[string]bool{
		"text/plain":       true,
		"text/html":        true,
		"application/json": true,
	}
	if !allowed[ct] {
		panic(errors.New("ValueError"))
	}

	w.Header().Set("Content-Type", ct)
}

func main() {
	passed := true

	// Helper to check if a function panics
	assertPanic := func(name string, f func()) {
		defer func() {
			if r := recover(); r != nil {
				// Expected panic
			} else {
				fmt.Printf("FAIL: %s - expected panic but did not get one\n", name)
				passed = false
			}
		}()
		f()
	}

	// Helper to create a request and run route
	runTest := func(name string, query string, expectPanic bool, expectedHeader string) {
		req := &http.Request{
			Method: "GET",
			URL:    &url.URL{Path: "/", RawQuery: query},
		}
		rr := httptest.NewRecorder()

		didPanic := false
		func() {
			defer func() {
				if r := recover(); r != nil {
					didPanic = true
				}
			}()
			route(rr, req)
		}()

		if expectPanic {
			if !didPanic {
				fmt.Printf("FAIL: %s - expected panic\n", name)
				passed = false
			}
		} else {
			if didPanic {
				fmt.Printf("FAIL: %s - unexpected panic\n", name)
				passed = false
			} else {
				got := rr.Header().Get("Content-Type")
				if got != expectedHeader {
					fmt.Printf("FAIL: %s - expected header '%s', got '%s'\n", name, expectedHeader, got)
					passed = false
				}
			}
		}
	}

	// 1) allowed
	runTest("Test 1 (allowed text/html)", "Content-Type=text/html", false, "text/html")

	// 2) allowed
	runTest("Test 2 (allowed text/plain)", "Content-Type=text/plain", false, "text/plain")

	// 3) reject CRLF injection
	// The query string is URL decoded by the server before reaching the handler.
	// %0D%0A decodes to \r\n.
	runTest("Test 3 (CRLF injection)", "Content-Type=text/html\r\nX-Evil:1", true, "")

	// 4) reject unknown
	runTest("Test 4 (unknown type)", "Content-Type=application/xml", true, "")

	// 5) missing
	runTest("Test 5 (missing)", "", true, "")

	// 6) extra arg rejected (nil request)
	assertPanic("Test 6 (nil request)", func() {
		route(nil, nil)
	})

	if !passed {
		os.Exit(1)
	}
}