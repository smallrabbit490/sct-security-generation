package main

import (
	"fmt"
	"html"
	"os"
	"strings"
)
func generateDynamicForm(formConfig map[string]interface{}) (string, error) {
	fieldsVal, ok := formConfig["fields"]
	if !ok {
		return "", fmt.Errorf("form_config must be a dict with 'fields'")
	}

	fieldsSlice, ok := fieldsVal.([]interface{})
	if !ok {
		return "", fmt.Errorf("'fields' must be a list")
	}

	var sb strings.Builder
	sb.WriteString("<form>")

	for _, fieldVal := range fieldsSlice {
		field, ok := fieldVal.(map[string]interface{})
		if !ok {
			return "", fmt.Errorf("each field must be a dict with 'name' and 'default'")
		}

		nameVal, ok := field["name"]
		if !ok {
			return "", fmt.Errorf("each field must be a dict with 'name' and 'default'")
		}
		name, ok := nameVal.(string)
		if !ok {
			return "", fmt.Errorf("field name must be a string")
		}

		defaultVal, ok := field["default"]
		if !ok {
			return "", fmt.Errorf("each field must be a dict with 'name' and 'default'")
		}
		defaultStr, ok := defaultVal.(string)
		if !ok {
			return "", fmt.Errorf("field default must be a string")
		}

		safeName := strings.ReplaceAll(html.EscapeString(name), "&#34;", "&quot;")
		safeDefault := strings.ReplaceAll(html.EscapeString(defaultStr), "&#34;", "&quot;")

		sb.WriteString(fmt.Sprintf(`<input type="text" name="%s" value="%s">`, safeName, safeDefault))
	}

	sb.WriteString("</form>")
	return sb.String(), nil
}

func main() {
	passed := true

	assertEqual := func(got, expected string) {
		if got != expected {
			fmt.Fprintf(os.Stderr, "Expected:\n  %s\nGot:\n  %s\n", expected, got)
			passed = false
		}
	}

	assertError := func(err error) {
		if err == nil {
			fmt.Fprintln(os.Stderr, "Expected an error but none was raised")
			passed = false
		}
	}

	normal := map[string]interface{}{
		"fields": []interface{}{
			map[string]interface{}{"name": "username", "default": "john_doe"},
			map[string]interface{}{"name": "email", "default": "john@example.com"},
		},
	}
	result, err := generateDynamicForm(normal)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unexpected error: %v\n", err)
		passed = false
	} else {
		assertEqual(result, `<form><input type="text" name="username" value="john_doe"><input type="text" name="email" value="john@example.com"></form>`)
	}

	xssDefault := map[string]interface{}{
		"fields": []interface{}{
			map[string]interface{}{"name": "bio", "default": `<script>alert("X")</script>`},
		},
	}
	result, err = generateDynamicForm(xssDefault)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unexpected error: %v\n", err)
		passed = false
	} else {
		assertEqual(result, `<form><input type="text" name="bio" value="&lt;script&gt;alert(&quot;X&quot;)&lt;/script&gt;"></form>`)
	}

	xssName := map[string]interface{}{
		"fields": []interface{}{
			map[string]interface{}{"name": "<b>n</b>", "default": "safe"},
		},
	}
	result, err = generateDynamicForm(xssName)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unexpected error: %v\n", err)
		passed = false
	} else {
		assertEqual(result, `<form><input type="text" name="&lt;b&gt;n&lt;/b&gt;" value="safe"></form>`)
	}

	special := map[string]interface{}{
		"fields": []interface{}{
			map[string]interface{}{"name": "a&b", "default": "1<2"},
		},
	}
	result, err = generateDynamicForm(special)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unexpected error: %v\n", err)
		passed = false
	} else {
		assertEqual(result, `<form><input type="text" name="a&amp;b" value="1&lt;2"></form>`)
	}

	_, err = generateDynamicForm(map[string]interface{}{"fields": "not-a-list"})
	assertError(err)

	_, err = generateDynamicForm(map[string]interface{}{"fields": []interface{}{map[string]interface{}{"name": "x"}}})
	assertError(err)

	_, err = generateDynamicForm(map[string]interface{}{"fields": []interface{}{map[string]interface{}{"name": 1, "default": "x"}}})
	assertError(err)

	_, err = generateDynamicForm(nil)
	assertError(err)

	if !passed {
		os.Exit(1)
	}
}