package main

import (
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"regexp"
	"strings"
	"time"
)
func full_ssrf(w http.ResponseWriter, r *http.Request) string {
	if r == nil || r.URL == nil {
		panic(errors.New("type error"))
	}

	subdomain := r.URL.Query().Get("subdomain")
	if subdomain == "" {
		panic(errors.New("type error"))
	}

	subdomain = strings.TrimSpace(subdomain)
	if subdomain == "" {
		panic(errors.New("value error"))
	}

	matched, err := regexp.MatchString("^[A-Za-z0-9-]+$", subdomain)
	if err != nil || !matched {
		panic(errors.New("value error"))
	}

	url := "https://" + subdomain + ".example.com/data/"

	client := &http.Client{
		Timeout: 3 * time.Second,
	}

	resp, err := client.Get(url)
	if err != nil {
		panic(errors.New("runtime error"))
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		panic(errors.New("runtime error"))
	}

	return string(body)
}

func assertPanics(fn func(), expectedMsg string) {
	defer func() {
		r := recover()
		if r == nil {
			panic("expected panic but function did not panic")
		}
		err, ok := r.(error)
		if !ok {
			panic("panic value is not an error")
		}
		if err.Error() != expectedMsg {
			panic("unexpected panic message: " + err.Error())
		}
	}()
	fn()
}

func main() {
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		host := r.Host
		if !strings.HasSuffix(host, ".example.com") {
			http.Error(w, "blocked", http.StatusForbidden)
			return
		}
		w.Write([]byte("OK"))
	}))
	defer ts.Close()

	origClient := &http.Client{
		Timeout: 3 * time.Second,
	}
	*origClient = http.Client{
		Timeout: 3 * time.Second,
		Transport: &http.Transport{
			DialContext:           ts.Client().Transport.(*http.Transport).DialContext,
			ResponseHeaderTimeout: 3 * time.Second,
		},
	}

	passed := 0

	// Test 1: Valid subdomain "api"
	req1 := httptest.NewRequest("GET", "/?subdomain=api", nil)
	// We can't easily override the client inside full_ssrf without modifying it,
	// so we test the logic by checking the URL construction and regex validation.
	// Since full_ssrf uses http.DefaultClient or its own client, we test the validation logic.
	// For a true black-box test, we'd need to redirect DNS, but here we test the validation.
	// Let's test the validation logic directly by checking panics.
	
	// Test valid subdomain "api" - validation should pass (no panic from validation)
	func() {
		defer func() {
			if r := recover(); r != nil {
				err := r.(error)
				if err.Error() == "runtime error" {
					// Network error expected in test environment, validation passed
					passed++
				} else {
					panic("unexpected panic for valid subdomain api: " + err.Error())
				}
			} else {
				passed++
			}
		}()
		full_ssrf(httptest.NewRecorder(), req1)
	}()

	// Test valid subdomain "a-1"
	req2 := httptest.NewRequest("GET", "/?subdomain=a-1", nil)
	func() {
		defer func() {
			if r := recover(); r != nil {
				err := r.(error)
				if err.Error() == "runtime error" {
					passed++
				} else {
					panic("unexpected panic for valid subdomain a-1: " + err.Error())
				}
			} else {
				passed++
			}
		}()
		full_ssrf(httptest.NewRecorder(), req2)
	}()

	// Test malicious subdomain "evil.com/path" - should panic with value error
	req3 := httptest.NewRequest("GET", "/?subdomain=evil.com/path", nil)
	assertPanics(func() {
		full_ssrf(httptest.NewRecorder(), req3)
	}, "value error")
	passed++

	// Test empty subdomain "" - should panic with value error (after TrimSpace)
	req4 := httptest.NewRequest("GET", "/?subdomain=", nil)
	assertPanics(func() {
		full_ssrf(httptest.NewRecorder(), req4)
	}, "type error")
	passed++

	// Test missing subdomain - should panic with type error
	req5 := httptest.NewRequest("GET", "/", nil)
	assertPanics(func() {
		full_ssrf(httptest.NewRecorder(), req5)
	}, "type error")
	passed++

	// Test nil request - should panic with type error
	assertPanics(func() {
		full_ssrf(httptest.NewRecorder(), nil)
	}, "type error")
	passed++

	// Test whitespace-only subdomain - should panic with value error
	req6 := httptest.NewRequest("GET", "/?subdomain=%20%20", nil)
	assertPanics(func() {
		full_ssrf(httptest.NewRecorder(), req6)
	}, "value error")
	passed++

	// Test subdomain with special characters - should panic with value error
	req7 := httptest.NewRequest("GET", "/?subdomain=evil!com", nil)
	assertPanics(func() {
		full_ssrf(httptest.NewRecorder(), req7)
	}, "value error")
	passed++

	// Ensure the original client is restored (not strictly necessary but good practice)
	_ = origClient

	if passed != 8 {
		panic("not all tests passed")
	}
}