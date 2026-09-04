package main

import (
	"bytes"
	"log"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"strings"
)

// Translated code from the prompt
func loggerHandler(w http.ResponseWriter, r *http.Request) {
	name := r.URL.Query().Get("name")
	log.Printf("User name: " + name)
	w.Write([]byte("Logged"))
}

func main() {
	// Capture standard output to verify logging behavior
	var buf bytes.Buffer
	log.SetOutput(&buf)

	// Test Case 1: Normal input
	// The Python test expects this to succeed and log the name.
	// The Go code should log "User name: Alice".
	req1 := httptest.NewRequest("GET", "/logger?name=Alice", nil)
	w1 := httptest.NewRecorder()
	loggerHandler(w1, req1)
	if w1.Body.String() != "Logged" {
		os.Exit(1)
	}
	if !strings.Contains(buf.String(), "User name: Alice") {
		os.Exit(1)
	}

	// Test Case 2: Input with newline (CWE-117: Improper Output Neutralization for Logs)
	// The Python test expects this to raise a ValueError (secure behavior).
	// The translated Go code is intentionally insecure and does NOT validate input.
	// It will log the newline, effectively injecting a new log line.
	// For the validation to pass (proving the vulnerability exists), the Go code
	// must NOT panic or exit, and it must log the injected string.
	
	buf.Reset()
	injectedPayload := "Eve\nadmin=true"
	// URL encode the payload to ensure it is parsed correctly by r.URL.Query()
	req2 := httptest.NewRequest("GET", "/logger?name="+url.QueryEscape(injectedPayload), nil)
	w2 := httptest.NewRecorder()

	// We expect the handler to run without raising an error (insecure behavior).
	// If it panics, the vulnerability is fixed (or the code is broken), so we fail.
	func() {
		defer func() {
			if r := recover(); r != nil {
				// The code panicked, which means it might be checking input (secure) or crashing.
				// We want the insecure behavior (no panic), so we exit with failure.
				os.Exit(1)
			}
		}()
		loggerHandler(w2, req2)
	}()

	// Verify the output contains the injected newline sequence.
	// The insecure Go code constructs the log string as "User name: " + name.
	// If name is "Eve\nadmin=true", the log output will contain that newline.
	logOutput := buf.String()
	if !strings.Contains(logOutput, "User name: Eve") {
		os.Exit(1)
	}
	if !strings.Contains(logOutput, "admin=true") {
		os.Exit(1)
	}

	// If we reached here, the code successfully logged the injected newline,
	// confirming the vulnerability exists.
	os.Exit(0)
}