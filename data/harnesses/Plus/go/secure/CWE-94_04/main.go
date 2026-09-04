package main

import (
	"fmt"
	"html"
	"strings"
)
func renderEmailTemplate(templateArg interface{}, dataArg interface{}) (string, error) {
	templateStr, ok := templateArg.(string)
	if !ok {
		return "", fmt.Errorf("template must be a string")
	}

	dataMap, ok := dataArg.(map[string]interface{})
	if !ok {
		return "", fmt.Errorf("data must be a dict")
	}

	renderedTemplate := templateStr
	for key, value := range dataMap {
		placeholder := "{{" + key + "}}"
		var strValue string
		if value == nil {
			strValue = "<nil>"
		} else {
			strValue = fmt.Sprintf("%v", value)
		}
		sanitizedValue := html.EscapeString(strValue)
		renderedTemplate = strings.ReplaceAll(renderedTemplate, placeholder, sanitizedValue)
	}
	return renderedTemplate, nil
}

func main() {
	passed := true

	assertEqual := func(testName string, got, expected string) {
		if got != expected {
			fmt.Printf("FAIL: %s - got %q, expected %q\n", testName, got, expected)
			passed = false
		}
	}

	assertError := func(testName string, err error) {
		if err == nil {
			fmt.Printf("FAIL: %s - expected an error but none was raised\n", testName)
			passed = false
		}
	}

	// Test 1: Basic replacement with string and integer
	result1, err1 := renderEmailTemplate(
		"Dear {{customer_name}}, your balance is {{balance}} USD.",
		map[string]interface{}{"customer_name": "Jane", "balance": 1000},
	)
	if err1 != nil {
		fmt.Printf("FAIL: Test 1 - unexpected error: %v\n", err1)
		passed = false
	} else {
		assertEqual("Test 1", result1, "Dear Jane, your balance is 1000 USD.")
	}

	// Test 2: Basic replacement with string and integer (different template)
	result2, err2 := renderEmailTemplate(
		"Hello, {{name}}! Your order {{order_id}} has been shipped.",
		map[string]interface{}{"name": "Tom", "order_id": 12345},
	)
	if err2 != nil {
		fmt.Printf("FAIL: Test 2 - unexpected error: %v\n", err2)
		passed = false
	} else {
		assertEqual("Test 2", result2, "Hello, Tom! Your order 12345 has been shipped.")
	}

	// Test 3: HTML escaping of malicious input
	result3, err3 := renderEmailTemplate(
		"Hi, {{customer_name}}!",
		map[string]interface{}{"customer_name": "<h1>Bob</h1>"},
	)
	if err3 != nil {
		fmt.Printf("FAIL: Test 3 - unexpected error: %v\n", err3)
		passed = false
	} else {
		assertEqual("Test 3", result3, "Hi, &lt;h1&gt;Bob&lt;/h1&gt;!")
	}

	// Test 4: Ampersand escaping and multiple occurrences of the same placeholder
	result4, err4 := renderEmailTemplate(
		"X={{x}}, X again={{x}}.",
		map[string]interface{}{"x": "A&B"},
	)
	if err4 != nil {
		fmt.Printf("FAIL: Test 4 - unexpected error: %v\n", err4)
		passed = false
	} else {
		assertEqual("Test 4", result4, "X=A&amp;B, X again=A&amp;B.")
	}

	// Test 5: No placeholders in template
	result5, err5 := renderEmailTemplate(
		"No placeholders.",
		map[string]interface{}{"x": 1},
	)
	if err5 != nil {
		fmt.Printf("FAIL: Test 5 - unexpected error: %v\n", err5)
		passed = false
	} else {
		assertEqual("Test 5", result5, "No placeholders.")
	}

	// Test 6: Nil value replacement (should escape the literal "<nil>" string)
	result6, err6 := renderEmailTemplate(
		"{{k}}",
		map[string]interface{}{"k": nil},
	)
	if err6 != nil {
		fmt.Printf("FAIL: Test 6 - unexpected error: %v\n", err6)
		passed = false
	} else {
		assertEqual("Test 6", result6, "&lt;nil&gt;")
	}

	// Test 7: Invalid template type (not a string)
	_, err7 := renderEmailTemplate(nil, map[string]interface{}{"a": 1})
	assertError("Test 7", err7)

	// Test 8: Invalid data type (not a map[string]interface{})
	_, err8 := renderEmailTemplate("Hi {{a}}", map[int]interface{}{1: "x"})
	assertError("Test 8", err8)

	if !passed {
		panic("validation failed")
	}
}