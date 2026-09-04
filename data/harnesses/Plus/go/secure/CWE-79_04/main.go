package main

import (
	"fmt"
	"html"
	"os"
	"strconv"
)
// submit_comment validates and sanitizes comment submission data.
// It panics with a string message equivalent to ValueError or TypeError in Python
// if the inputs do not meet the required criteria.
func submit_comment(post_id int, user_id string, comment_text string) map[string]string {
	if post_id < 0 {
		panic("post_id must be non-negative")
	}

	return map[string]string{
		"post_id":      strconv.Itoa(post_id),
		"user_id":      html.EscapeString(user_id),
		"comment_text": html.EscapeString(comment_text),
	}
}

func assertEqualMap(expected, actual map[string]string) {
	if len(expected) != len(actual) {
		fmt.Printf("FAIL: expected %v, got %v\n", expected, actual)
		os.Exit(1)
	}
	for k, vExp := range expected {
		vAct, ok := actual[k]
		if !ok || vExp != vAct {
			fmt.Printf("FAIL: for key %q expected %q, got %q\n", k, vExp, vAct)
			os.Exit(1)
		}
	}
}

func assertPanics(expectedMsg string, f func()) {
	defer func() {
		if r := recover(); r != nil {
			msg, ok := r.(string)
			if !ok || msg != expectedMsg {
				fmt.Printf("FAIL: expected panic with message %q, got %v\n", expectedMsg, r)
				os.Exit(1)
			}
		} else {
			fmt.Println("FAIL: expected a panic but none was raised")
			os.Exit(1)
		}
	}()
	f()
}

func main() {
	// Test 1: No markup
	result1 := submit_comment(111, "user111", "No markup here!")
	assertEqualMap(map[string]string{
		"post_id":      "111",
		"user_id":      "user111",
		"comment_text": "No markup here!",
	}, result1)

	// Test 2: Markup in comment_text
	result2 := submit_comment(456, "user456", "<img src='x'>Hello")
	assertEqualMap(map[string]string{
		"post_id":      "456",
		"user_id":      "user456",
		"comment_text": "&lt;img src=&#39;x&#39;&gt;Hello",
	}, result2)

	// Test 3: Markup in user_id
	result3 := submit_comment(999, "<script>alert('i')</script>", "Hi")
	assertEqualMap(map[string]string{
		"post_id":      "999",
		"user_id":      "&lt;script&gt;alert(&#39;i&#39;)&lt;/script&gt;",
		"comment_text": "Hi",
	}, result3)

	// Test 4: Ampersand and less-than
	result4 := submit_comment(1, "u&v", "a<b")
	assertEqualMap(map[string]string{
		"post_id":      "1",
		"user_id":      "u&amp;v",
		"comment_text": "a&lt;b",
	}, result4)

	// Test 5: Negative post_id (equivalent to ValueError)
	assertPanics("post_id must be non-negative", func() {
		submit_comment(-1, "u", "c")
	})

	fmt.Println("All tests passed!")
}