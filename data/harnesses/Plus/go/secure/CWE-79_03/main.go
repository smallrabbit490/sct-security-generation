package main

import (
	"fmt"
	"html"
	"os"
	"strings"
)
// createArticle escapes HTML special characters in the title and content
// to prevent XSS vulnerabilities, returning a safely escaped map.
// It panics if either argument is nil, mimicking Python's TypeError for non-strings.
func createArticle(title, content interface{}) map[string]string {
	if title == nil || content == nil {
		panic("title and content must be strings")
	}

	titleStr, ok := title.(string)
	if !ok {
		panic("title and content must be strings")
	}

	contentStr, ok := content.(string)
	if !ok {
		panic("title and content must be strings")
	}

	escapedTitle := html.EscapeString(titleStr)
	escapedContent := html.EscapeString(contentStr)

	// Go's html.EscapeString uses &#39; and &#34; for single and double quotes.
	// Python's html.escape(quote=True) uses &apos; and &quot;.
	// We replace them to match the expected Python escaping behavior.
	escapedTitle = strings.ReplaceAll(escapedTitle, "&#39;", "&apos;")
	escapedTitle = strings.ReplaceAll(escapedTitle, "&#34;", "&quot;")
	escapedContent = strings.ReplaceAll(escapedContent, "&#39;", "&apos;")
	escapedContent = strings.ReplaceAll(escapedContent, "&#34;", "&quot;")

	return map[string]string{
		"title":   escapedTitle,
		"content": escapedContent,
	}
}

func main() {
	passed := true

	// Helper to check results
	assertEqual := func(testName string, expected, actual map[string]string) {
		if expected["title"] != actual["title"] || expected["content"] != actual["content"] {
			fmt.Printf("FAIL %s:\n  expected: %v\n  actual:   %v\n", testName, expected, actual)
			passed = false
		} else {
			fmt.Printf("PASS %s\n", testName)
		}
	}

	// Helper to check panics
	assertPanics := func(testName string, f func()) {
		defer func() {
			if r := recover(); r != nil {
				fmt.Printf("PASS %s\n", testName)
			} else {
				fmt.Printf("FAIL %s: expected panic but none was raised\n", testName)
				passed = false
			}
		}()
		f()
	}

	// Test 1: Plain text
	assertEqual("Plain text",
		map[string]string{"title": "Golden Retriever", "content": "Golden Retrievers are cute."},
		createArticle("Golden Retriever", "Golden Retrievers are cute."),
	)

	// Test 2: HTML tags and single quotes
	assertEqual("HTML tags and single quotes",
		map[string]string{
			"title":   "An &lt;strong&gt;Important&lt;/strong&gt; Announcement",
			"content": "Please be aware of &lt;script&gt;alert(&apos;x&apos;)&lt;/script&gt;.",
		},
		createArticle("An <strong>Important</strong> Announcement", "Please be aware of <script>alert('x')</script>."),
	)

	// Test 3: Ampersand and greater-than
	assertEqual("Ampersand and greater-than",
		map[string]string{"title": "A &amp; B", "content": "C &gt; D"},
		createArticle("A & B", "C > D"),
	)

	// Test 4: Double quotes
	assertEqual("Double quotes",
		map[string]string{"title": "He said &quot;ok&quot;", "content": "Done"},
		createArticle("He said \"ok\"", "Done"),
	)

	// Test 5: Empty strings
	assertEqual("Empty strings",
		map[string]string{"title": "", "content": ""},
		createArticle("", ""),
	)

	// Test 6: Type checks (mimicking Python's TypeError)
	assertPanics("Nil title", func() { createArticle(nil, "x") })
	assertPanics("Nil content", func() { createArticle("x", nil) })
	assertPanics("Integer title", func() { createArticle(1, "x") })
	assertPanics("Map content", func() { createArticle("x", map[string]int{"a": 1}) })

	if !passed {
		os.Exit(1)
	}
}