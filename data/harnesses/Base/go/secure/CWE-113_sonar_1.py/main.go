package main

import (
	"errors"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
)
func route(w http.ResponseWriter, r *http.Request) {
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

func assertPanic(fn func(), expectedErr string) {
	defer func() {
		r := recover()
		if r == nil {
			os.Stderr.WriteString("expected panic but did not panic\n")
			os.Exit(1)
		}
		err, ok := r.(error)
		if !ok {
			os.Stderr.WriteString("panic did not return an error\n")
			os.Exit(1)
		}
		if err.Error() != expectedErr {
			os.Stderr.WriteString("panic error mismatch\n")
			os.Exit(1)
		}
	}()
	fn()
}

func assertNoPanic(fn func()) {
	defer func() {
		r := recover()
		if r != nil {
			os.Stderr.WriteString("expected no panic but panicked\n")
			os.Exit(1)
		}
	}()
	fn()
}

func main() {
	// 1) allowed content-type
	req1 := httptest.NewRequest(http.MethodGet, "/route?Content-Type=text/plain", nil)
	rec1 := httptest.NewRecorder()
	assertNoPanic(func() { route(rec1, req1) })
	if rec1.Header().Get("Content-Type") != "text/plain" {
		os.Stderr.WriteString("Content-Type header mismatch for text/plain\n")
		os.Exit(1)
	}

	// 2) another allowed
	req2 := httptest.NewRequest(http.MethodGet, "/route?Content-Type=application/json", nil)
	rec2 := httptest.NewRecorder()
	assertNoPanic(func() { route(rec2, req2) })
	if rec2.Header().Get("Content-Type") != "application/json" {
		os.Stderr.WriteString("Content-Type header mismatch for application/json\n")
		os.Exit(1)
	}

	// 3) reject header injection (CRLF)
	req3 := httptest.NewRequest(http.MethodGet, "/route?Content-Type=text/plain%0D%0AX-Evil%3A1", nil)
	rec3 := httptest.NewRecorder()
	assertPanic(func() { route(rec3, req3) }, "ValueError")

	// 4) reject unknown type
	req4 := httptest.NewRequest(http.MethodGet, "/route?Content-Type=application/xml", nil)
	rec4 := httptest.NewRecorder()
	assertPanic(func() { route(rec4, req4) }, "ValueError")

	// 5) missing Content-Type
	req5 := httptest.NewRequest(http.MethodGet, "/route", nil)
	rec5 := httptest.NewRecorder()
	assertPanic(func() { route(rec5, req5) }, "ValueError")

	os.Exit(0)
}