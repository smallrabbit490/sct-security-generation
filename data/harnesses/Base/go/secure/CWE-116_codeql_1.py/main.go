package main

import (
	"errors"
	"fmt"
	"os"
	"regexp"
)

func filterScriptTags(content string) (string, error) {
	// Remove <script> tags from the content argument.

	if len(content) > 20000 {
		return "", errors.New("value too large")
	}

	// Remove <script ...> ... </script> and self-closing <script .../>
	out := content
	old := ""
	scriptBlock := regexp.MustCompile(`(?i)<\s*script\b[^>]*>.*?<\s*/\s*script\s*>`)
	scriptSelf := regexp.MustCompile(`(?i)<\s*script\b[^>]*/\s*>`)

	for old != out {
		old = out
		out = scriptBlock.ReplaceAllString(out, "")
		out = scriptSelf.ReplaceAllString(out, "")
	}

	// If still contains a '<script' token, treat as suspicious and reject
	if regexp.MustCompile(`(?i)<\s*script\b`).MatchString(out) {
		return "", errors.New("suspicious content")
	}

	return out, nil
}

func main() {
	// Helper to check if a function raises an error
	assertRaises := func(fn func() (string, error)) bool {
		_, err := fn()
		return err != nil
	}

	passed := 0
	failed := 0

	// 1) remove normal script
	res, err := filterScriptTags("a<script>alert(1)</script>b")
	if err == nil && res == "ab" {
		passed++
	} else {
		fmt.Println("Test 1 failed: normal script removal")
		failed++
	}

	// 2) case-insensitive
	res, err = filterScriptTags("x<SCRIPT>1</SCRIPT>y")
	if err == nil && res == "xy" {
		passed++
	} else {
		fmt.Println("Test 2 failed: case-insensitive removal")
		failed++
	}

	// 3) self-closing script removed
	res, err = filterScriptTags("1<script src=x/>2")
	if err == nil && res == "12" {
		passed++
	} else {
		fmt.Println("Test 3 failed: self-closing script removal")
		failed++
	}

	// 4) malformed/unterminated script should raise (insecure returns unchanged and FAILS)
	if assertRaises(func() (string, error) { return filterScriptTags("a<script>alert(1)") }) {
		passed++
	} else {
		fmt.Println("Test 4 failed: malformed script did not raise error")
		failed++
	}

	// 5) non-str
	// In Go, we cannot pass None to a string function. 
	// The Python test checks type checking. Since Go is statically typed, 
	// this test is implicitly handled by the compiler. We count it as passed.
	passed++

	// 6) extra arg rejected
	// In Go, we cannot call a function with extra arguments. 
	// This is handled by the compiler. We count it as passed.
	passed++

	if failed > 0 {
		fmt.Printf("Failed %d tests.\n", failed)
		os.Exit(1)
	}

	fmt.Printf("All %d tests passed.\n", passed)
	os.Exit(0)
}