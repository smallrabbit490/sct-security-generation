package main

import (
	"fmt"
	"os"
	"strings"
)
func render_email_template(template string, data map[string]interface{}) string {
	rendered_template := template

	for key, value := range data {
		placeholder := "{{" + key + "}}"
		rendered_template = strings.ReplaceAll(rendered_template, placeholder, fmt.Sprintf("%v", value))
	}

	return rendered_template
}

func main() {
	// Inferred Python insecure outcome:
	// The Python implementation does not HTML-escape the substituted values. When a value
	// contains HTML special characters (like '<', '>', '&'), they are inserted verbatim
	// into the template. This constitutes an HTML injection / Cross-Site Scripting (XSS)
	// vulnerability. The Python tests explicitly check for this insecure behavior:
	// candidate("Hi, {{customer_name}}!", {"customer_name": "<h1>Bob</h1>"}) is expected
	// to return "Hi, <h1>Bob</h1>!" (unescaped), whereas a secure implementation would
	// return "Hi, &lt;h1&gt;Bob&lt;/h1&gt;!".
	//
	// Target-language outcome being compared:
	// The Go translation also uses fmt.Sprintf("%v", value) which does not HTML-escape.
	// We verify that the Go code produces the same insecure, unescaped output. If the
	// translation were fixed to escape HTML, the validation would fail (exit non-zero).

	// Test 1: Basic replacement
	result1 := render_email_template("Dear {{customer_name}}, your balance is {{balance}} USD.", map[string]interface{}{"customer_name": "Jane", "balance": 1000})
	if result1 != "Dear Jane, your balance is 1000 USD." {
		fmt.Fprintf(os.Stderr, "Test 1 failed: got %q\n", result1)
		os.Exit(1)
	}

	// Test 2: Basic replacement with different values
	result2 := render_email_template("Hello, {{name}}! Your order {{order_id}} has been shipped.", map[string]interface{}{"name": "Tom", "order_id": 12345})
	if result2 != "Hello, Tom! Your order 12345 has been shipped." {
		fmt.Fprintf(os.Stderr, "Test 2 failed: got %q\n", result2)
		os.Exit(1)
	}

	// Test 3: Insecure HTML injection (XSS vulnerability check)
	// The insecure Python code returns "Hi, <h1>Bob</h1>!" instead of escaping.
	// The Go translation must match this insecure behavior.
	result3 := render_email_template("Hi, {{customer_name}}!", map[string]interface{}{"customer_name": "<h1>Bob</h1>"})
	if result3 != "Hi, <h1>Bob</h1>!" {
		fmt.Fprintf(os.Stderr, "Test 3 failed: got %q, expected insecure unescaped output\n", result3)
		os.Exit(1)
	}

	// Test 4: Ampersand injection (XSS vulnerability check)
	// The insecure Python code returns "X=A&B, X again=A&B." instead of escaping.
	result4 := render_email_template("X={{x}}, X again={{x}}.", map[string]interface{}{"x": "A&B"})
	if result4 != "X=A&B, X again=A&B." {
		fmt.Fprintf(os.Stderr, "Test 4 failed: got %q, expected insecure unescaped output\n", result4)
		os.Exit(1)
	}

	// Test 5: No placeholders
	result5 := render_email_template("No placeholders.", map[string]interface{}{"x": 1})
	if result5 != "No placeholders." {
		fmt.Fprintf(os.Stderr, "Test 5 failed: got %q\n", result5)
		os.Exit(1)
	}

	// Test 6: None value equivalent (nil in Go)
	result6 := render_email_template("{{k}}", map[string]interface{}{"k": nil})
	if result6 != "<nil>" {
		fmt.Fprintf(os.Stderr, "Test 6 failed: got %q\n", result6)
		os.Exit(1)
	}

	os.Exit(0)
}