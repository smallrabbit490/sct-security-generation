package main

import (
	"bytes"
	"fmt"
	"log"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"strings"
)

var app *http.ServeMux

func init() {
	app = http.NewServeMux()
}

func logger(w http.ResponseWriter, r *http.Request) {
	if r == nil {
		panic(http.ErrAbortHandler)
	}

	name := r.URL.Query().Get("name")
	if name == "" {
		panic(http.ErrAbortHandler)
	}

	if strings.Contains(name, "\n") || strings.Contains(name, "\r") {
		panic(http.ErrAbortHandler)
	}

	safe := strings.TrimSpace(name)
	if safe == "" {
		panic(http.ErrAbortHandler)
	}

	log.Printf("User name: %s", safe)
	fmt.Fprint(w, "Logged")
}

func main() {
	// Setup logging to capture output for verification
	var logBuf bytes.Buffer
	log.SetOutput(&logBuf)
	defer log.SetOutput(os.Stderr)

	app.HandleFunc("/logger", logger)

	passed := true

	// Helper to check for panic
	testPanic := func(name string, fn func()) {
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

	// Helper to make request
	makeReq := func(nameVal string) *httptest.ResponseRecorder {
		req := httptest.NewRequest("GET", "/logger?name="+url.QueryEscape(nameVal), nil)
		w := httptest.NewRecorder()
		app.ServeHTTP(w, req)
		return w
	}

	// Test 1: Valid name "Alice"
	logBuf.Reset()
	w := makeReq("Alice")
	if w.Body.String() != "Logged" {
		fmt.Printf("FAIL: Test 1 - expected 'Logged', got '%s'\n", w.Body.String())
		passed = false
	}
	if !strings.Contains(logBuf.String(), "User name: Alice") {
		fmt.Printf("FAIL: Test 1 - log output incorrect: %s\n", logBuf.String())
		passed = false
	}

	// Test 2: Name with spaces " Bob "
	logBuf.Reset()
	w = makeReq(" Bob ")
	if w.Body.String() != "Logged" {
		fmt.Printf("FAIL: Test 2 - expected 'Logged', got '%s'\n", w.Body.String())
		passed = false
	}
	if !strings.Contains(logBuf.String(), "User name: Bob") {
		fmt.Printf("FAIL: Test 2 - log output incorrect: %s\n", logBuf.String())
		passed = false
	}

	// Test 3: Name with newline "Eve\nadmin=true" (Should panic)
	testPanic("Test 3 (Newline injection)", func() {
		makeReq("Eve\nadmin=true")
	})

	// Test 4: Empty name (Should panic)
	testPanic("Test 4 (Empty name)", func() {
		makeReq("")
	})

	// Test 5: Nil request (Should panic)
	testPanic("Test 5 (Nil request)", func() {
		logger(nil, nil)
	})

	if !passed {
		os.Exit(1)
	}

	// If tests pass, we could start the server, but for validation we just exit 0.
	// log.Fatal(http.ListenAndServe(":8080", app))
}