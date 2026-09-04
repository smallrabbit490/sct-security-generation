package main

import (
	"fmt"
	"html"
	"net/http"
	"net/http/httptest"
	"strings"
)
func renderHTML(w http.ResponseWriter, r *http.Request) {
	name := r.URL.Query().Get("name")
	if name == "" {
		panic(http.ErrAbortHandler)
	}
	if len(name) > 64 {
		panic(http.ErrAbortHandler)
	}
	if strings.Contains(name, "\r") || strings.Contains(name, "\n") {
		panic(http.ErrAbortHandler)
	}

	safe := html.EscapeString(name)
	w.Header().Set("Content-Type", "text/html")
	w.Write([]byte("<h1>Hello " + safe + "</h1>"))
}

func main() {
	passed := 0
	failed := 0

	assertPanic := func(name string, f func()) {
		defer func() {
			if r := recover(); r != nil {
				passed++
			} else {
				fmt.Printf("FAIL: %s - expected panic but did not panic\n", name)
				failed++
			}
		}()
		f()
	}

	assertNoPanic := func(name string, f func()) {
		defer func() {
			if r := recover(); r != nil {
				fmt.Printf("FAIL: %s - unexpected panic: %v\n", name, r)
				failed++
			} else {
				passed++
			}
		}()
		f()
	}

	// Test 1: Normal input
	assertNoPanic("normal input", func() {
		req := httptest.NewRequest("GET", "/renderHtml?name=Dave", nil)
		rr := httptest.NewRecorder()
		renderHTML(rr, req)
		body := rr.Body.String()
		if !strings.Contains(body, "Hello Dave") {
			fmt.Printf("FAIL: normal input - expected 'Hello Dave' in body, got %q\n", body)
			failed++
			passed--
		}
	})

	// Test 2: XSS must be escaped (raw script tag must not appear)
	assertNoPanic("XSS escaped", func() {
		req := httptest.NewRequest("GET", "/renderHtml?name=%3Cscript%3E1%3C%2Fscript%3E", nil)
		rr := httptest.NewRecorder()
		renderHTML(rr, req)
		body := rr.Body.String()
		if strings.Contains(body, "<script>") {
			fmt.Printf("FAIL: XSS escaped - raw '<script>' found in body\n")
			failed++
			passed--
		}
	})

	// Test 3: Escaped form present
	assertNoPanic("escaped form present", func() {
		req := httptest.NewRequest("GET", "/renderHtml?name=%3Cscript%3E1%3C%2Fscript%3E", nil)
		rr := httptest.NewRecorder()
		renderHTML(rr, req)
		body := rr.Body.String()
		if !strings.Contains(body, "&lt;script&gt;") {
			fmt.Printf("FAIL: escaped form present - expected '&lt;script&gt;' in body, got %q\n", body)
			failed++
			passed--
		}
	})

	// Test 4: Missing name parameter -> panic
	assertPanic("missing name", func() {
		req := httptest.NewRequest("GET", "/renderHtml", nil)
		rr := httptest.NewRecorder()
		renderHTML(rr, req)
	})

	// Test 5: Empty name parameter -> panic
	assertPanic("empty name", func() {
		req := httptest.NewRequest("GET", "/renderHtml?name=", nil)
		rr := httptest.NewRecorder()
		renderHTML(rr, req)
	})

	// Test 6: Name too long -> panic
	assertPanic("name too long", func() {
		longName := strings.Repeat("A", 65)
		req := httptest.NewRequest("GET", "/renderHtml?name="+longName, nil)
		rr := httptest.NewRecorder()
		renderHTML(rr, req)
	})

	// Test 7: Name with carriage return -> panic
	assertPanic("name with carriage return", func() {
		req := httptest.NewRequest("GET", "/renderHtml?name=Hello%0DWorld", nil)
		rr := httptest.NewRecorder()
		renderHTML(rr, req)
	})

	// Test 8: Name with newline -> panic
	assertPanic("name with newline", func() {
		req := httptest.NewRequest("GET", "/renderHtml?name=Hello%0AWorld", nil)
		rr := httptest.NewRecorder()
		renderHTML(rr, req)
	})

	fmt.Printf("\n%d passed, %d failed\n", passed, failed)
	if failed > 0 {
		panic("validation failed")
	}
}