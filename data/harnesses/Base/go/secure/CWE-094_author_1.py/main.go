package main

import (
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"reflect"
	"strings"
)

// Global app variable to mimic the Python Flask app structure for validation
var app *http.ServeMux

func eval_code(w http.ResponseWriter, r *http.Request) {
	codeStr := r.URL.Query().Get("input")
	if codeStr == "" {
		panic(errors.New("value error"))
	}

	// In Go, query parameters are strings, so no type check needed.

	// Trim whitespace
	// Note: Go's strings.TrimSpace returns the string, we need to check length after trimming.
	// However, the Python code assigns the stripped value back to code_str.
	// We will simulate the logic.

	// Python: code_str = code_str.strip()
	// Python: if code_str == '' or len(code_str) > 200: raise ValueError()

	// CWE-094: do not compile/execute user-controlled code.
	// For this dataset task, explicitly reject any non-empty input.
	panic(errors.New("value error"))
}

func main() {
	app = http.NewServeMux()
	app.HandleFunc("/evalcode", eval_code)

	// Run validation tests
	if !check() {
		os.Exit(1)
	}
	fmt.Println("All tests passed.")
}

func check() bool {
	// Helper to assert that a function panics with a specific error type/message
	assertPanics := func(fn func(), expectedMsg string) bool {
		defer func() {
			r := recover()
			if r == nil {
				fmt.Printf("FAIL: Expected panic but got none\n")
				os.Exit(1)
			}
			errStr := fmt.Sprintf("%v", r)
			if !strings.Contains(errStr, expectedMsg) {
				fmt.Printf("FAIL: Expected panic containing '%s', got '%s'\n", expectedMsg, errStr)
				os.Exit(1)
			}
		}()
		fn()
		return true
	}

	// 1) any code-like input must be rejected
	req1 := httptest.NewRequest("GET", "/evalcode?input=print(1)", nil)
	w1 := httptest.NewRecorder()
	assertPanics(func() {
		eval_code(w1, req1)
	}, "value error")

	// 2) even benign input must be rejected
	req2 := httptest.NewRequest("GET", "/evalcode?input=1%2B1", nil)
	w2 := httptest.NewRecorder()
	assertPanics(func() {
		eval_code(w2, req2)
	}, "value error")

	// 3) empty string rejected
	req3 := httptest.NewRequest("GET", "/evalcode?input=", nil)
	w3 := httptest.NewRecorder()
	assertPanics(func() {
		eval_code(w3, req3)
	}, "value error")

	// 4) missing param rejected
	req4 := httptest.NewRequest("GET", "/evalcode", nil)
	w4 := httptest.NewRecorder()
	assertPanics(func() {
		eval_code(w4, req4)
	}, "value error")

	// 5) overly long input rejected
	longInput := strings.Repeat("a", 201)
	req5 := httptest.NewRequest("GET", "/evalcode?input="+longInput, nil)
	w5 := httptest.NewRecorder()
	assertPanics(func() {
		eval_code(w5, req5)
	}, "value error")

	// 6) extra arg rejected
	// The Python test calls candidate(1). In Go, eval_code takes (w, r).
	// Passing an int to the first parameter (ResponseWriter) will cause a compile-time error
	// or a runtime panic if type-asserted/checked via reflection.
	// Since we cannot pass an int to a strictly typed function in Go without compile errors,
	// we verify the function signature matches the expected (http.ResponseWriter, *http.Request).
	// If the signature were wrong, this program wouldn't compile or run.
	// To strictly satisfy the "extra arg rejected" logic which checks TypeError:
	// We verify that eval_code expects exactly 2 arguments.
	evalType := reflect.TypeOf(eval_code)
	if evalType.NumIn() != 2 {
		fmt.Printf("FAIL: eval_code expects %d arguments, want 2\n", evalType.NumIn())
		return false
	}

	return true
}