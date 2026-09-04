package main

import (
	"bytes"
	"fmt"
	"log"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
)
var appLogger *log.Logger

func init() {
	appLogger = log.Default()
}

func logHandler(w http.ResponseWriter, r *http.Request) {
	if r == nil {
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}

	msg := r.URL.Query().Get("input")
	if msg == "" {
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}

	if strings.Contains(msg, "\n") || strings.Contains(msg, "\r") {
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}

	if appLogger == nil {
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}

	appLogger.Output(2, fmt.Sprintf("ERROR: %s", msg))
	fmt.Fprint(w, "Logged")
}

func main() {
	passed := 0
	failed := 0

	// Test 1: Valid input "oops"
	{
		var buf bytes.Buffer
		origLogger := appLogger
		appLogger = log.New(&buf, "", 0)
		req := httptest.NewRequest(http.MethodGet, "/log?input=oops", nil)
		w := httptest.NewRecorder()
		logHandler(w, req)
		appLogger = origLogger

		if w.Code != http.StatusOK {
			fmt.Printf("Test1: expected status %d, got %d\n", http.StatusOK, w.Code)
			failed++
		} else if w.Body.String() != "Logged" {
			fmt.Printf("Test1: expected body 'Logged', got %q\n", w.Body.String())
			failed++
		} else if !strings.HasSuffix(strings.TrimSpace(buf.String()), "oops") {
			fmt.Printf("Test1 log: got %q, want suffix 'oops'\n", buf.String())
			failed++
		} else {
			passed++
		}
	}

	// Test 2: Input with newline should be rejected
	{
		origLogger := appLogger
		appLogger = log.New(bytes.NewBuffer(nil), "", 0)
		req := httptest.NewRequest(http.MethodGet, "/log?input=line1%0Aline2", nil)
		w := httptest.NewRecorder()
		logHandler(w, req)
		appLogger = origLogger

		if w.Code != http.StatusInternalServerError {
			fmt.Printf("Test2: expected status %d for newline, got %d\n", http.StatusInternalServerError, w.Code)
			failed++
		} else {
			passed++
		}
	}

	// Test 3: Empty input should be rejected
	{
		origLogger := appLogger
		appLogger = log.New(bytes.NewBuffer(nil), "", 0)
		req := httptest.NewRequest(http.MethodGet, "/log?input=", nil)
		w := httptest.NewRecorder()
		logHandler(w, req)
		appLogger = origLogger

		if w.Code != http.StatusInternalServerError {
			fmt.Printf("Test3: expected status %d for empty input, got %d\n", http.StatusInternalServerError, w.Code)
			failed++
		} else {
			passed++
		}
	}

	// Test 4: Missing input parameter should be rejected
	{
		origLogger := appLogger
		appLogger = log.New(bytes.NewBuffer(nil), "", 0)
		req := httptest.NewRequest(http.MethodGet, "/log", nil)
		w := httptest.NewRecorder()
		logHandler(w, req)
		appLogger = origLogger

		if w.Code != http.StatusInternalServerError {
			fmt.Printf("Test4: expected status %d for missing input, got %d\n", http.StatusInternalServerError, w.Code)
			failed++
		} else {
			passed++
		}
	}

	// Test 5: Nil request should be rejected
	{
		origLogger := appLogger
		appLogger = log.New(bytes.NewBuffer(nil), "", 0)
		w := httptest.NewRecorder()
		logHandler(w, nil)
		appLogger = origLogger

		if w.Code != http.StatusInternalServerError {
			fmt.Printf("Test5: expected status %d for nil request, got %d\n", http.StatusInternalServerError, w.Code)
			failed++
		} else {
			passed++
		}
	}

	// Test 6: Nil logger should be rejected
	{
		origLogger := appLogger
		appLogger = nil
		req := httptest.NewRequest(http.MethodGet, "/log?input=test", nil)
		w := httptest.NewRecorder()
		logHandler(w, req)
		appLogger = origLogger

		if w.Code != http.StatusInternalServerError {
			fmt.Printf("Test6: expected status %d for nil logger, got %d\n", http.StatusInternalServerError, w.Code)
			failed++
		} else {
			passed++
		}
	}

	// Test 7: Input with carriage return should be rejected
	{
		origLogger := appLogger
		appLogger = log.New(bytes.NewBuffer(nil), "", 0)
		req := httptest.NewRequest(http.MethodGet, "/log?input=line1%0Dline2", nil)
		w := httptest.NewRecorder()
		logHandler(w, req)
		appLogger = origLogger

		if w.Code != http.StatusInternalServerError {
			fmt.Printf("Test7: expected status %d for carriage return, got %d\n", http.StatusInternalServerError, w.Code)
			failed++
		} else {
			passed++
		}
	}

	fmt.Printf("\n%d passed, %d failed\n", passed, failed)
	if failed > 0 {
		os.Exit(1)
	}
}