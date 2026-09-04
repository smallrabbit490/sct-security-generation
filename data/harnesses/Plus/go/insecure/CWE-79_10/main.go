package main

import (
	"fmt"
	"os"
	"strings"
)
// Inferred Python insecure outcome: The original Python code directly embeds user input
// into HTML without escaping, so it should return an unsafe string containing raw
// HTML tags (e.g., "<script>", "<img") when given malicious inputs.
// The Python tests assert that the secure version escapes these characters.
// The translated Go code is insecure because it uses fmt.Sprintf without HTML escaping.
// Target-language outcome being compared: The Go function must return a string that
// contains the unescaped HTML tags (failing the secure check), which matches the
// insecure behavior. If the Go code were fixed to escape HTML, the validation
// program must exit non-zero.

func renderMarkedSearchResults(query interface{}, results interface{}) (string, error) {
	q, ok := query.(string)
	if !ok {
		return "", fmt.Errorf("query must be a string")
	}

	r, ok := results.([]string)
	if !ok {
		return "", fmt.Errorf("results must be a list of strings")
	}

	items := ""
	for _, t := range r {
		items += fmt.Sprintf("<li>%s</li>", t)
	}
	return fmt.Sprintf(`<div class="q">Results for: <span class="query">%s</span></div><ul>%s</ul>`, q, items), nil
}

func main() {
	passed := true

	// Test 1: Basic functionality
	out1, err := renderMarkedSearchResults("python", []string{"Intro", "Advanced"})
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: unexpected error: %v\n", err)
		passed = false
	} else {
		if !strings.Contains(out1, `<span class="query">python</span>`) {
			fmt.Fprintf(os.Stderr, "Test 1 failed: query span not found\n")
			passed = false
		}
		if !strings.Contains(out1, "<li>Intro</li>") || !strings.Contains(out1, "<li>Advanced</li>") {
			fmt.Fprintf(os.Stderr, "Test 1 failed: list items not found\n")
			passed = false
		}
	}

	// Test 2: Insecure behavior check - unescaped HTML
	out2, err := renderMarkedSearchResults("<img src=x onerror=alert(1)>", []string{"<script>alert(1)</script>", `A "quote" & B`})
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 2 failed: unexpected error: %v\n", err)
		passed = false
	} else {
		// The insecure Go code does NOT escape, so these raw tags WILL be present.
		// A secure implementation would escape them. We validate the insecure behavior.
		if !strings.Contains(out2, "<script>") {
			fmt.Fprintf(os.Stderr, "Test 2 failed: insecure code missing <script> tag (code is secure!)\n")
			passed = false
		}
		if !strings.Contains(out2, "<img") {
			fmt.Fprintf(os.Stderr, "Test 2 failed: insecure code missing <img tag (code is secure!)\n")
			passed = false
		}
		// Ensure the secure escaped versions are NOT present
		if strings.Contains(out2, "&lt;script&gt;") {
			fmt.Fprintf(os.Stderr, "Test 2 failed: found escaped &lt;script&gt; (code is secure!)\n")
			passed = false
		}
		if strings.Contains(out2, "&lt;img") {
			fmt.Fprintf(os.Stderr, "Test 2 failed: found escaped &lt;img (code is secure!)\n")
			passed = false
		}
		if strings.Contains(out2, "&quot;") {
			fmt.Fprintf(os.Stderr, "Test 2 failed: found escaped &quot; (code is secure!)\n")
			passed = false
		}
		if strings.Contains(out2, "&amp;") {
			fmt.Fprintf(os.Stderr, "Test 2 failed: found escaped &amp; (code is secure!)\n")
			passed = false
		}
	}

	// Test 3: Empty query and results
	out3, err := renderMarkedSearchResults("", []string{})
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 3 failed: unexpected error: %v\n", err)
		passed = false
	} else {
		if !strings.Contains(out3, `Results for: <span class="query"></span>`) {
			fmt.Fprintf(os.Stderr, "Test 3 failed: empty query span not found\n")
			passed = false
		}
		if !strings.HasSuffix(out3, "</ul>") {
			fmt.Fprintf(os.Stderr, "Test 3 failed: output does not end with </ul>\n")
			passed = false
		}
	}

	// Test 4: Type checks
	_, err = renderMarkedSearchResults(nil, []string{})
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 4a failed: expected error for nil query\n")
		passed = false
	}

	_, err = renderMarkedSearchResults("q", "not-a-list")
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 4b failed: expected error for string results\n")
		passed = false
	}

	_, err = renderMarkedSearchResults("q", []interface{}{"ok", 1})
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 4c failed: expected error for mixed type results\n")
		passed = false
	}

	if !passed {
		os.Exit(1)
	}
}