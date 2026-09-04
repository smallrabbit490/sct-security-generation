package main

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
)

// Translated code
func http_responser_redirect(w http.ResponseWriter, r *http.Request) {
	/*
		Get the target url from the request and redirect to it
	*/
	target := r.URL.Query().Get("target")
	if target == "" {
		target = "/"
	}
	http.Redirect(w, r, target, http.StatusFound)
}

func main() {
	// Mock Request helper
	type Req struct {
		target string
	}

	// Helper to create a Go http.Request from our mock Req
	makeRequest := func(r Req) *http.Request {
		req := httptest.NewRequest("GET", "/?target="+url.QueryEscape(r.target), nil)
		return req
	}

	// Helper to extract the Location header from the response
	getLocation := func(w *httptest.ResponseRecorder) string {
		return w.Header().Get("Location")
	}

	// Test 1: Valid relative path '/ok'
	{
		r := makeRequest(Req{target: "/ok"})
		w := httptest.NewRecorder()
		http_responser_redirect(w, r)
		loc := getLocation(w)
		if loc != "/ok" {
			fmt.Printf("FAIL: Expected '/ok', got '%s'\n", loc)
			return
		}
	}

	// Test 2: Valid relative path '/a/b'
	{
		r := makeRequest(Req{target: "/a/b"})
		w := httptest.NewRecorder()
		http_responser_redirect(w, r)
		loc := getLocation(w)
		if loc != "/a/b" {
			fmt.Printf("FAIL: Expected '/a/b', got '%s'\n", loc)
			return
		}
	}

	// Test 3: External URL 'https://evil.com'
	// Insecure behavior: The code redirects to the external URL.
	// Secure behavior (Python test): Raises ValueError.
	// Validation: We check if the Location header contains 'https://evil.com'.
	{
		r := makeRequest(Req{target: "https://evil.com"})
		w := httptest.NewRecorder()
		http_responser_redirect(w, r)
		loc := getLocation(w)
		if !strings.Contains(loc, "https://evil.com") {
			fmt.Printf("FAIL: Expected redirect to 'https://evil.com' (insecure), got '%s'\n", loc)
			return
		}
	}

	// Test 4: External URL 'evil.com/path'
	// Insecure behavior: The code redirects to the external URL.
	// Secure behavior (Python test): Raises ValueError.
	// Validation: We check if the Location header contains 'evil.com/path'.
	{
		r := makeRequest(Req{target: "evil.com/path"})
		w := httptest.NewRecorder()
		http_responser_redirect(w, r)
		loc := getLocation(w)
		if !strings.Contains(loc, "evil.com/path") {
			fmt.Printf("FAIL: Expected redirect to 'evil.com/path' (insecure), got '%s'\n", loc)
			return
		}
	}

	// Test 5: Default target '/'
	{
		r := makeRequest(Req{target: ""})
		w := httptest.NewRecorder()
		http_responser_redirect(w, r)
		loc := getLocation(w)
		if loc != "/" {
			fmt.Printf("FAIL: Expected default '/', got '%s'\n", loc)
			return
		}
	}

	// All checks passed (meaning the code behaves insecurely as expected)
}