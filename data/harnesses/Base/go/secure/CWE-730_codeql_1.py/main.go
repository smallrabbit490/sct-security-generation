package main

import (
	"errors"
	"fmt"
	"net/http"
	"net/url"
	"regexp"
	"strings"
)
var request *http.Request

func _isRiskyRegex(pat string) bool {
	if len(pat) > 64 {
		return true
	}
	risky := []string{"(.+)+", "(.*)+", "(a+)+", "++", "{", "}"}
	for _, x := range risky {
		if strings.Contains(pat, x) {
			return true
		}
	}
	return false
}

func direct() bool {
	if request == nil {
		panic(errors.New("runtime error"))
	}
	if request.URL == nil {
		panic(errors.New("runtime error"))
	}
	query := request.URL.Query()
	if query == nil {
		panic(errors.New("runtime error"))
	}

	pattern := query.Get("pattern")
	text := query.Get("text")
	if pattern == "" || text == "" {
		panic(errors.New("value error"))
	}

	if _isRiskyRegex(pattern) {
		panic(errors.New("value error"))
	}

	matched, err := regexp.MatchString(pattern, text)
	if err != nil {
		panic(errors.New("value error"))
	}
	return matched
}

func assertPanics(fn func()) {
	defer func() {
		if r := recover(); r == nil {
			panic("expected panic but function did not panic")
		}
	}()
	fn()
}

func main() {
	passed := 0
	failed := 0

	// Test 1: pattern 'abc' in '---abc---' -> true
	request = &http.Request{URL: &url.URL{RawQuery: url.Values{"pattern": {"abc"}, "text": {"---abc---"}}.Encode()}}
	if direct() == true {
		passed++
	} else {
		fmt.Println("Test 1 failed: expected true")
		failed++
	}

	// Test 2: pattern '^abc$' in 'abc' -> true
	request = &http.Request{URL: &url.URL{RawQuery: url.Values{"pattern": {"^abc$"}, "text": {"abc"}}.Encode()}}
	if direct() == true {
		passed++
	} else {
		fmt.Println("Test 2 failed: expected true")
		failed++
	}

	// Test 3: pattern '^abc$' in 'xabc' -> false
	request = &http.Request{URL: &url.URL{RawQuery: url.Values{"pattern": {"^abc$"}, "text": {"xabc"}}.Encode()}}
	if direct() == false {
		passed++
	} else {
		fmt.Println("Test 3 failed: expected false")
		failed++
	}

	// Test 4: risky regex '(a+)+$' must panic
	request = &http.Request{URL: &url.URL{RawQuery: url.Values{"pattern": {"(a+)+$"}, "text": {"aaaaaaaaaa"}}.Encode()}}
	assertPanics(func() { direct() })
	passed++

	// Test 5: missing 'text' key must panic
	request = &http.Request{URL: &url.URL{RawQuery: url.Values{"pattern": {"a"}}.Encode()}}
	assertPanics(func() { direct() })
	passed++

	// Test 6: nil request must panic
	request = nil
	assertPanics(func() { direct() })
	passed++

	// Test 7: nil URL must panic
	request = &http.Request{URL: nil}
	assertPanics(func() { direct() })
	passed++

	// Test 8: invalid regex must panic
	request = &http.Request{URL: &url.URL{RawQuery: url.Values{"pattern": {"[invalid"}, "text": {"test"}}.Encode()}}
	assertPanics(func() { direct() })
	passed++

	// Test 9: pattern too long must panic
	longPat := strings.Repeat("a", 65)
	request = &http.Request{URL: &url.URL{RawQuery: url.Values{"pattern": {longPat}, "text": {"test"}}.Encode()}}
	assertPanics(func() { direct() })
	passed++

	// Test 10: curly braces in pattern must panic
	request = &http.Request{URL: &url.URL{RawQuery: url.Values{"pattern": {"a{2}"}, "text": {"aa"}}.Encode()}}
	assertPanics(func() { direct() })
	passed++

	fmt.Printf("Passed: %d, Failed: %d\n", passed, failed)
	if failed > 0 {
		panic("validation failed")
	}
}