package main

import (
	"fmt"
	"os"
	"reflect"
)
// htmlEscape replaces special characters with their HTML entity equivalents.
// It matches the behavior of Python's html.escape(s, quote=True).
func htmlEscape(s string, escapeQuotes bool) string {
	var buf []rune
	for _, c := range s {
		switch c {
		case '&':
			buf = append(buf, '&', 'a', 'm', 'p', ';')
		case '<':
			buf = append(buf, '&', 'l', 't', ';')
		case '>':
			buf = append(buf, '&', 'g', 't', ';')
		case '"':
			if escapeQuotes {
				buf = append(buf, '&', 'q', 'u', 'o', 't', ';')
			} else {
				buf = append(buf, c)
			}
		case '\'':
			if escapeQuotes {
				buf = append(buf, '&', '#', '3', '9', ';')
			} else {
				buf = append(buf, c)
			}
		default:
			buf = append(buf, c)
		}
	}
	return string(buf)
}

// createProfile takes user_id, full_name, and bio as interface{} types to
// strictly validate their types (simulating Python's isinstance checks),
// escapes any HTML markup, and returns a mapped profile dictionary.
func createProfile(userId interface{}, fullName interface{}, bio interface{}) (map[string]string, error) {
	uid, ok := userId.(string)
	if !ok {
		return nil, fmt.Errorf("all fields must be strings")
	}
	fname, ok := fullName.(string)
	if !ok {
		return nil, fmt.Errorf("all fields must be strings")
	}
	b, ok := bio.(string)
	if !ok {
		return nil, fmt.Errorf("all fields must be strings")
	}

	return map[string]string{
		"user_id":   htmlEscape(uid, true),
		"full_name": htmlEscape(fname, true),
		"bio":       htmlEscape(b, true),
	}, nil
}

func main() {
	passed := true

	// assertRaises checks that calling createProfile with the given args returns an error.
	assertRaises := func(userId, fullName, bio interface{}) {
		_, err := createProfile(userId, fullName, bio)
		if err == nil {
			fmt.Printf("FAIL: Expected an error for inputs %v, %v, %v but got none\n", userId, fullName, bio)
			passed = false
		}
	}

	// Test 1: No markup
	result, err := createProfile("user111", "Charlie Brown", "No markup here!")
	if err != nil {
		fmt.Printf("FAIL: Unexpected error: %v\n", err)
		passed = false
	} else {
		expected := map[string]string{"user_id": "user111", "full_name": "Charlie Brown", "bio": "No markup here!"}
		if !reflect.DeepEqual(result, expected) {
			fmt.Printf("FAIL: Expected %v, got %v\n", expected, result)
			passed = false
		}
	}

	// Test 2: Malicious image tag in bio
	result, err = createProfile("user456", "Jane Smith", "<img src='malicious.jpg'>This is another bio.")
	if err != nil {
		fmt.Printf("FAIL: Unexpected error: %v\n", err)
		passed = false
	} else {
		expected := map[string]string{"user_id": "user456", "full_name": "Jane Smith", "bio": "&lt;img src=&#39;malicious.jpg&#39;&gt;This is another bio."}
		if !reflect.DeepEqual(result, expected) {
			fmt.Printf("FAIL: Expected %v, got %v\n", expected, result)
			passed = false
		}
	}

	// Test 3: Script tag in user_id
	result, err = createProfile("<script>alert('x')</script>", "Alice Davis", "This is a normal bio.")
	if err != nil {
		fmt.Printf("FAIL: Unexpected error: %v\n", err)
		passed = false
	} else {
		expected := map[string]string{"user_id": "&lt;script&gt;alert(&#39;x&#39;)&lt;/script&gt;", "full_name": "Alice Davis", "bio": "This is a normal bio."}
		if !reflect.DeepEqual(result, expected) {
			fmt.Printf("FAIL: Expected %v, got %v\n", expected, result)
			passed = false
		}
	}

	// Test 4: Various special characters
	result, err = createProfile("u&v", "A<B", "He said \"ok\"")
	if err != nil {
		fmt.Printf("FAIL: Unexpected error: %v\n", err)
		passed = false
	} else {
		expected := map[string]string{"user_id": "u&amp;v", "full_name": "A&lt;B", "bio": "He said &quot;ok&quot;"}
		if !reflect.DeepEqual(result, expected) {
			fmt.Printf("FAIL: Expected %v, got %v\n", expected, result)
			passed = false
		}
	}

	// Test 5: Type errors (simulating Python's TypeError)
	assertRaises(nil, "Name", "Bio")
	assertRaises("u", nil, "Bio")
	assertRaises("u", "Name", nil)
	assertRaises(1, "Name", "Bio")

	if !passed {
		os.Exit(1)
	}
	os.Exit(0)
}