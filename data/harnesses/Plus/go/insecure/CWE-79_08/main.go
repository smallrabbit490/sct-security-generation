package main

import (
	"fmt"
	"os"
)
// The translated insecure Go code (as provided).
// Inferred Python insecure outcome: The function directly interpolates unescaped
// user-controlled strings into HTML, resulting in Cross-Site Scripting (XSS).
// It produces raw HTML containing dangerous characters like '<', '>', '"', and '&'
// instead of their safely escaped equivalents ('&lt;', '&gt;', '&quot;', '&amp;').
// The target-language outcome being compared: The Go translation must similarly
// produce unescaped HTML output for XSS payloads, failing the secure test expectations.
func generateDynamicForm(formConfig map[string]interface{}) (string, error) {
	fieldsVal, ok := formConfig["fields"]
	if !ok {
		return "", fmt.Errorf("missing 'fields' key in form_config")
	}

	fieldsSlice, ok := fieldsVal.([]interface{})
	if !ok {
		return "", fmt.Errorf("'fields' must be a list")
	}

	formHTML := "<form>"
	for _, fieldVal := range fieldsSlice {
		field, ok := fieldVal.(map[string]interface{})
		if !ok {
			return "", fmt.Errorf("each field must be a dictionary")
		}

		nameVal, ok := field["name"]
		if !ok {
			return "", fmt.Errorf("missing 'name' key in field")
		}
		name, ok := nameVal.(string)
		if !ok {
			return "", fmt.Errorf("'name' must be a string")
		}

		defaultVal, ok := field["default"]
		if !ok {
			return "", fmt.Errorf("missing 'default' key in field")
		}
		defaultStr, ok := defaultVal.(string)
		if !ok {
			return "", fmt.Errorf("'default' must be a string")
		}

		formHTML += fmt.Sprintf(`<input type="text" name="%s" value="%s">`, name, defaultStr)
	}
	formHTML += "</form>"
	return formHTML, nil
}

func main() {
	passed := true

	// Test 1: Normal input (should pass for both secure and insecure code)
	normal := map[string]interface{}{
		"fields": []interface{}{
			map[string]interface{}{"name": "username", "default": "john_doe"},
			map[string]interface{}{"name": "email", "default": "john@example.com"},
		},
	}
	expectedNormal := `<form><input type="text" name="username" value="john_doe"><input type="text" name="email" value="john@example.com"></form>`
	resultNormal, err := generateDynamicForm(normal)
	if err != nil || resultNormal != expectedNormal {
		fmt.Printf("Test 1 failed: got %q, err %v\n", resultNormal, err)
		passed = false
	}

	// Test 2: XSS default value
	// Secure expectation: value="&lt;script&gt;alert(&quot;X&quot;)&lt;/script&gt;"
	// Insecure expectation (our target): value="<script>alert("X")</script>"
	xssDefault := map[string]interface{}{
		"fields": []interface{}{
			map[string]interface{}{"name": "bio", "default": `<script>alert("X")</script>`},
		},
	}
	expectedInsecureXSS := `<form><input type="text" name="bio" value="<script>alert("X")</script>"></form>`
	resultXSS, err := generateDynamicForm(xssDefault)
	if err != nil || resultXSS != expectedInsecureXSS {
		fmt.Printf("Test 2 failed: got %q, err %v\n", resultXSS, err)
		passed = false
	}

	// Test 3: XSS name value
	// Secure expectation: name="&lt;b&gt;n&lt;/b&gt;"
	// Insecure expectation (our target): name="<b>n</b>"
	xssName := map[string]interface{}{
		"fields": []interface{}{
			map[string]interface{}{"name": "<b>n</b>", "default": "safe"},
		},
	}
	expectedInsecureName := `<form><input type="text" name="<b>n</b>" value="safe"></form>`
	resultName, err := generateDynamicForm(xssName)
	if err != nil || resultName != expectedInsecureName {
		fmt.Printf("Test 3 failed: got %q, err %v\n", resultName, err)
		passed = false
	}

	// Test 4: Special characters
	// Secure expectation: name="a&amp;b" value="1&lt;2"
	// Insecure expectation (our target): name="a&b" value="1<2"
	special := map[string]interface{}{
		"fields": []interface{}{
			map[string]interface{}{"name": "a&b", "default": "1<2"},
		},
	}
	expectedInsecureSpecial := `<form><input type="text" name="a&b" value="1<2"></form>`
	resultSpecial, err := generateDynamicForm(special)
	if err != nil || resultSpecial != expectedInsecureSpecial {
		fmt.Printf("Test 4 failed: got %q, err %v\n", resultSpecial, err)
		passed = false
	}

	// Test 5: Error handling for invalid 'fields' type
	invalidFields := map[string]interface{}{
		"fields": "not-a-list",
	}
	_, err = generateDynamicForm(invalidFields)
	if err == nil {
		fmt.Println("Test 5 failed: expected an error for invalid 'fields' type, got nil")
		passed = false
	}

	// Test 6: Error handling for missing 'default' key
	missingDefault := map[string]interface{}{
		"fields": []interface{}{
			map[string]interface{}{"name": "x"},
		},
	}
	_, err = generateDynamicForm(missingDefault)
	if err == nil {
		fmt.Println("Test 6 failed: expected an error for missing 'default' key, got nil")
		passed = false
	}

	// Test 7: Error handling for invalid 'name' type
	invalidName := map[string]interface{}{
		"fields": []interface{}{
			map[string]interface{}{"name": 1, "default": "x"},
		},
	}
	_, err = generateDynamicForm(invalidName)
	if err == nil {
		fmt.Println("Test 7 failed: expected an error for invalid 'name' type, got nil")
		passed = false
	}

	// Test 8: Error handling for nil input
	_, err = generateDynamicForm(nil)
	if err == nil {
		fmt.Println("Test 8 failed: expected an error for nil input, got nil")
		passed = false
	}

	if !passed {
		os.Exit(1)
	}
}