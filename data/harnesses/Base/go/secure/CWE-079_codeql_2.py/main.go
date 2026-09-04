package main

import (
	"fmt"
	"html"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
)

// name is the translated handler function.
func name(w http.ResponseWriter, r *http.Request) {
	raw := r.URL.Query().Get("name")
	if raw == "" {
		panic(http.ErrAbortHandler)
	}

	if len(raw) > 64 {
		panic(http.ErrAbortHandler)
	}

	// Prevent header/body splitting patterns
	for _, c := range raw {
		if c == '\r' || c == '\n' {
			panic(http.ErrAbortHandler)
		}
	}

	safe := html.EscapeString(raw)
	w.Write([]byte("Your name is " + safe))
}

func main() {
	// Define a helper to run the handler and capture the response.
	runHandler := func(query string) (string, int, bool) {
		req := httptest.NewRequest("GET", "/showName"+query, nil)
		w := httptest.NewRecorder()
		panicked := false

		func() {
			defer func() {
				if r := recover(); r != nil {
					panicked = true
				}
			}()
			name(w, req)
		}()

		return w.Body.String(), w.Code, panicked
	}

	passed := true

	// 1) normal value
	body, _, panicked := runHandler("?name=Bob")
	if panicked || body != "Your name is Bob" {
		fmt.Println("FAIL: Test 1 - normal value")
		passed = false
	}

	// 2) XSS payload must be escaped
	body, _, panicked = runHandler("?name=%3Cimg%20src%3Dx%20onerror%3D1%3E")
	if panicked || strings.Contains(body, "<img") {
		fmt.Println("FAIL: Test 2 - XSS payload escaped")
		passed = false
	}

	// 3) escaped form present
	body, _, panicked = runHandler("?name=%3Cimg%20src%3Dx%20onerror%3D1%3E")
	if panicked || !strings.Contains(body, "&lt;img") {
		fmt.Println("FAIL: Test 3 - escaped form present")
		passed = false
	}

	// 4) missing param -> exception
	_, _, panicked = runHandler("")
	if !panicked {
		fmt.Println("FAIL: Test 4 - missing param exception")
		passed = false
	}

	// 5) CRLF -> exception
	_, _, panicked = runHandler("?name=ok%0D%0Aevil")
	if !panicked {
		fmt.Println("FAIL: Test 5 - CRLF exception")
		passed = false
	}

	// 6) too long -> exception
	longName := strings.Repeat("a", 65)
	_, _, panicked = runHandler("?name=" + longName)
	if !panicked {
		fmt.Println("FAIL: Test 6 - too long exception")
		passed = false
	}

	// 7) extra arg rejected
	// In Go, the handler signature is fixed. We verify the function exists and is callable.
	// The Python test checks TypeError for calling with extra args.
	// Since we cannot call name(1) in Go (compile error), we assume this structural check passes.

	if !passed {
		os.Exit(1)
	}
}