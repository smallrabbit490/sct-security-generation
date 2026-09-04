package main

import (
	"fmt"
	"html"
	"os"
	"reflect"
	"strings"
)
// display_comment generates an HTML snippet for showing a comment.
// It escapes any HTML markup characters in the input to prevent XSS.
// It returns an error if the provided comment_text is not of type string.
func display_comment(comment_text interface{}) (string, error) {
	if reflect.TypeOf(comment_text) != reflect.TypeOf("") {
		return "", fmt.Errorf("comment_text must be a string")
	}

	text := comment_text.(string)
	encoded_comment_text := html.EscapeString(text)
	encoded_comment_text = strings.ReplaceAll(encoded_comment_text, "&#34;", "&quot;")
	encoded_comment_text = strings.ReplaceAll(encoded_comment_text, "&#39;", "&#x27;")

	var result strings.Builder
	result.WriteString("<b>Comment: ")
	result.WriteString(encoded_comment_text)
	result.WriteString("<br>")
	return result.String(), nil
}

func main() {
	passed := true

	assertEqual := func(expected, actual string) {
		if expected != actual {
			fmt.Printf("FAIL: expected %q, got %q\n", expected, actual)
			passed = false
		}
	}

	assertRaises := func(arg interface{}) {
		_, err := display_comment(arg)
		if err == nil {
			fmt.Printf("FAIL: expected an error for input %v, but got none\n", arg)
			passed = false
		}
	}

	// Test safe comments
	res, err := display_comment("This is a safe comment.")
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		passed = false
	} else {
		assertEqual("<b>Comment: This is a safe comment.<br>", res)
	}

	res, err = display_comment("Another safe comment.")
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		passed = false
	} else {
		assertEqual("<b>Comment: Another safe comment.<br>", res)
	}

	// Test script injection (XSS)
	res, err = display_comment("<script>alert('Test')</script>")
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		passed = false
	} else {
		assertEqual("<b>Comment: &lt;script&gt;alert(&#x27;Test&#x27;)&lt;/script&gt;<br>", res)
	}

	// Test quotes and ampersand
	res, err = display_comment(`He said "ok" & left`)
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		passed = false
	} else {
		assertEqual("<b>Comment: He said &quot;ok&quot; &amp; left<br>", res)
	}

	// Test invalid types raising errors
	assertRaises(nil)
	assertRaises(123)
	assertRaises([]string{"x"})
	assertRaises(map[string]int{"a": 1})

	if !passed {
		os.Exit(1)
	}

	fmt.Println("All tests passed!")
}