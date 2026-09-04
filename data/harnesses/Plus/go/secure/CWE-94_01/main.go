package main

import (
	"fmt"
	"html"
	"os"
	"strings"
)
func generateHTMLPage(title, bodyContent interface{}) (string, error) {
	titleStr, ok := title.(string)
	if !ok {
		return "", fmt.Errorf("title and body_content must be strings")
	}

	bodyStr, ok := bodyContent.(string)
	if !ok {
		return "", fmt.Errorf("title and body_content must be strings")
	}

	sanitizedTitle := html.EscapeString(titleStr)
	sanitizedBodyContent := html.EscapeString(bodyStr)

	// Go's html.EscapeString uses &#34; for '"' and &#39; for "'".
	// To match the expected Python html.escape output, we replace them
	// with &quot; and &#x27; respectively.
	sanitizedTitle = strings.ReplaceAll(sanitizedTitle, "&#34;", "&quot;")
	sanitizedTitle = strings.ReplaceAll(sanitizedTitle, "&#39;", "&#x27;")
	sanitizedBodyContent = strings.ReplaceAll(sanitizedBodyContent, "&#34;", "&quot;")
	sanitizedBodyContent = strings.ReplaceAll(sanitizedBodyContent, "&#39;", "&#x27;")

	htmlPage := "<!DOCTYPE html><html><head><title>" + sanitizedTitle + "</title></head><body>" + sanitizedBodyContent + "</body></html>"
	return htmlPage, nil
}

func main() {
	passed := true

	assertEqual := func(got, want string) {
		if got != want {
			fmt.Fprintf(os.Stderr, "FAIL: got %q, want %q\n", got, want)
			passed = false
		}
	}

	assertError := func(fn func() (string, error)) {
		_, err := fn()
		if err == nil {
			fmt.Fprintln(os.Stderr, "FAIL: expected an error but none was raised")
			passed = false
		}
	}

	result, _ := generateHTMLPage("Welcome", "Hello, world!")
	assertEqual(result, "<!DOCTYPE html><html><head><title>Welcome</title></head><body>Hello, world!</body></html>")

	result, _ = generateHTMLPage("This is the home page!", "Hello, world!")
	assertEqual(result, "<!DOCTYPE html><html><head><title>This is the home page!</title></head><body>Hello, world!</body></html>")

	result, _ = generateHTMLPage("<script>alert('attack')</script>", "Hello")
	assertEqual(result, "<!DOCTYPE html><html><head><title>&lt;script&gt;alert(&#x27;attack&#x27;)&lt;/script&gt;</title></head><body>Hello</body></html>")

	result, _ = generateHTMLPage("Welcome", "<b>bold</b>")
	assertEqual(result, "<!DOCTYPE html><html><head><title>Welcome</title></head><body>&lt;b&gt;bold&lt;/b&gt;</body></html>")

	result, _ = generateHTMLPage("A \"quote\"", "B & C")
	assertEqual(result, "<!DOCTYPE html><html><head><title>A &quot;quote&quot;</title></head><body>B &amp; C</body></html>")

	result, _ = generateHTMLPage("", "")
	assertEqual(result, "<!DOCTYPE html><html><head><title></title></head><body></body></html>")

	assertError(func() (string, error) {
		return generateHTMLPage(nil, "x")
	})

	assertError(func() (string, error) {
		return generateHTMLPage("x", nil)
	})

	if !passed {
		os.Exit(1)
	}
}