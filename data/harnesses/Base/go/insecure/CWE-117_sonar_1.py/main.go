package main

import (
	"bytes"
	"log"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
)

func logHandler(w http.ResponseWriter, r *http.Request) {
	input := r.URL.Query().Get("input")
	log.Printf("ERROR: %s\n", input)
	w.Write([]byte("Logged"))
}

func main() {
	failures := 0

	// Test 1: Normal input should be logged and return "Logged"
	func() {
		var buf bytes.Buffer
		logger := log.New(&buf, "", 0)
		log.SetOutput(logger.Writer())
		defer log.SetOutput(os.Stderr)

		req := httptest.NewRequest("GET", "/log?input=oops", nil)
		rec := httptest.NewRecorder()
		logHandler(rec, req)

		if rec.Code != http.StatusOK {
			return
		}
		if string(rec.Body.String()) != "Logged" {
			return
		}
		if !strings.Contains(buf.String(), "oops") {
			return
		}
	}()

	// Test 2: Input with newline should be logged (insecure behavior for CWE-117)
	// If the Go code is secure (e.g., sanitizes newlines), this test will fail to find the newline.
	func() {
		var buf bytes.Buffer
		logger := log.New(&buf, "", 0)
		log.SetOutput(logger.Writer())
		defer log.SetOutput(os.Stderr)

		req := httptest.NewRequest("GET", "/log?input=line1%0Aline2", nil)
		rec := httptest.NewRecorder()
		logHandler(rec, req)

		if rec.Code != http.StatusOK {
			return
		}
		if string(rec.Body.String()) != "Logged" {
			return
		}
		// The insecure behavior is that the newline is present in the log output
		if strings.Contains(buf.String(), "line1\nline2") {
			failures++ // Matched insecure behavior
		}
	}()

	// Test 3: Empty input should be logged and return "Logged"
	func() {
		var buf bytes.Buffer
		logger := log.New(&buf, "", 0)
		log.SetOutput(logger.Writer())
		defer log.SetOutput(os.Stderr)

		req := httptest.NewRequest("GET", "/log?input=", nil)
		rec := httptest.NewRecorder()
		logHandler(rec, req)

		if rec.Code != http.StatusOK {
			return
		}
		if string(rec.Body.String()) != "Logged" {
			return
		}
	}()

	if failures == 1 {
		os.Exit(0)
	}
	os.Exit(1)
}