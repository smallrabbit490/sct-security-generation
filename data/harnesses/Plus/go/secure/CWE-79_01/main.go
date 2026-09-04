package main

import (
	"fmt"
	"html"
	"reflect"
	"strings"
)
func generatePost(title, content string) string {
	safeTitle := strings.ReplaceAll(html.EscapeString(title), "&#34;", "&quot;")
	safeContent := strings.ReplaceAll(html.EscapeString(content), "&#34;", "&quot;")
	return fmt.Sprintf("<html><head><title>%s</title></head><body>%s</body></html>", safeTitle, safeContent)
}

func main() {
	passed := true

	assertEqual := func(expected, got string) {
		if expected != got {
			fmt.Printf("Expected:\n  %s\nGot:\n  %s\n", expected, got)
			passed = false
		}
	}

	assertPanics := func(fn func()) {
		defer func() {
			if r := recover(); r == nil {
				fmt.Println("Expected a panic but none was raised")
				passed = false
			}
		}()
		fn()
	}

	// Test 1: Normal strings
	assertEqual(
		"<html><head><title>This is a book title.</title></head><body>This book is about a dog.</body></html>",
		generatePost("This is a book title.", "This book is about a dog."),
	)

	// Test 2: HTML tags and single quotes
	assertEqual(
		"<html><head><title>&lt;script&gt;alert(&#x27;X&#x27;)&lt;/script&gt;</title></head><body>&lt;b&gt;hi&lt;/b&gt;</body></html>",
		generatePost("<script>alert('X')</script>", "<b>hi</b>"),
	)

	// Test 3: Ampersand and double quotes
	assertEqual(
		"<html><head><title>A &amp; B</title></head><body>He said &quot;ok&quot;</body></html>",
		generatePost("A & B", "He said \"ok\""),
	)

	// Test 4: Angle brackets
	assertEqual(
		"<html><head><title>&lt;&lt;</title></head><body>&gt;&gt;</body></html>",
		generatePost("<<", ">>"),
	)

	// Test 5: Type checks (simulating Python's TypeError by passing interface{})
	generatePostInterface := func(title, content interface{}) (string, error) {
		titleStr, ok := title.(string)
		if !ok {
			return "", fmt.Errorf("title must be a string, got %v", reflect.TypeOf(title))
		}
		contentStr, ok := content.(string)
		if !ok {
			return "", fmt.Errorf("content must be a string, got %v", reflect.TypeOf(content))
		}
		return generatePost(titleStr, contentStr), nil
	}

	assertPanics(func() {
		title, content := interface{}(nil), interface{}("x")
		if _, err := generatePostInterface(title, content); err != nil {
			panic(err)
		}
	})

	assertPanics(func() {
		title, content := interface{}("x"), interface{}(nil)
		if _, err := generatePostInterface(title, content); err != nil {
			panic(err)
		}
	})

	assertPanics(func() {
		title, content := interface{}(123), interface{}("x")
		if _, err := generatePostInterface(title, content); err != nil {
			panic(err)
		}
	})

	assertPanics(func() {
		title, content := interface{}("x"), interface{}([]string{"y"})
		if _, err := generatePostInterface(title, content); err != nil {
			panic(err)
		}
	})

	if !passed {
		fmt.Println("FAIL")
	} else {
		fmt.Println("PASS")
	}
}