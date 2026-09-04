package main

import (
	"fmt"
	"os"
	"strings"
)
// renderProfilePage is the translated insecure Go function.
// Insecure behavior: It performs direct string substitution without HTML escaping,
// allowing XSS payloads to be injected into the rendered template.
func renderProfilePage(profileData map[string]interface{}) (string, error) {
	templateStr, ok := profileData["profile_template"].(string)
	if !ok {
		return "", fmt.Errorf("missing or invalid profile_template")
	}

	pageData, ok := profileData["page_data"].(map[string]interface{})
	if !ok {
		return "", fmt.Errorf("missing or invalid page_data")
	}

	result := templateStr
	for key, val := range pageData {
		placeholder := "{" + key + "}"
		valueStr := fmt.Sprintf("%v", val)
		result = strings.ReplaceAll(result, placeholder, valueStr)
	}

	return result, nil
}

func main() {
	// Inferred Python insecure outcome:
	// The original Python code uses str.format(**page_data), which directly substitutes
	// values into the template without HTML escaping. When provided with a value
	// containing HTML markup (e.g., '<script>alert("X")</script>'), it returns the
	// raw unescaped string (e.g., '<div><script>alert("X")</script></div>').
	// The Python tests assert that a SECURE implementation would escape these
	// characters (e.g., to '&lt;script&gt;...'), meaning the insecure Python code
	// FAILS the secure test assertions.
	//
	// Target-language outcome being compared:
	// We check if the Go translation also fails the secure test by returning the
	// unescaped, unsafe string. If the Go code returns the unescaped string, it
	// matches the insecure behavior (exits 0). If it returns the escaped string
	// (fixing the vulnerability), it does not match (exits non-zero).

	bioWithMarkup := map[string]interface{}{
		"profile_template": "<div>{bio}</div>",
		"page_data": map[string]interface{}{
			"bio": `<script>alert("X")</script>`,
		},
	}

	result, err := renderProfilePage(bioWithMarkup)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unexpected error: %v\n", err)
		os.Exit(1)
	}

	// The secure test expects the escaped string:
	// "<div>&lt;script&gt;alert(&quot;X&quot;)&lt;/script&gt;</div>"
	// The insecure implementation produces the unescaped string:
	// "<div><script>alert(\"X\")</script></div>"
	secureExpected := `<div>&lt;script&gt;alert(&quot;X&quot;)&lt;/script&gt;</div>`
	insecureExpected := `<div><script>alert("X")</script></div>`

	if result == secureExpected {
		// The vulnerability was fixed; the code is secure. Exit non-zero.
		fmt.Fprintf(os.Stderr, "Validation failed: code is secure (escaped output), expected insecure (unescaped output)\n")
		os.Exit(1)
	}

	if result == insecureExpected {
		// The code is insecure and matches the original Python behavior. Exit 0.
		os.Exit(0)
	}

	// The output matches neither expected string; exit non-zero.
	fmt.Fprintf(os.Stderr, "Validation failed: unexpected output\nGot: %s\n", result)
	os.Exit(1)
}