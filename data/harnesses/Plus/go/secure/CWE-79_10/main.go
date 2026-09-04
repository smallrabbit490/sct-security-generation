package main

import (
	"fmt"
	"html"
	"strings"
)
func renderMarkedSearchResults(query interface{}, results interface{}) (string, error) {
	queryStr, ok := query.(string)
	if !ok {
		return "", fmt.Errorf("query must be a string")
	}

	resultsSlice, ok := results.([]string)
	if !ok {
		return "", fmt.Errorf("results must be a list")
	}

	safeQuery := html.EscapeString(queryStr)

	safeItems := make([]string, 0, len(resultsSlice))
	for _, t := range resultsSlice {
		safeItems = append(safeItems, "<li>"+html.EscapeString(t)+"</li>")
	}

	return "<div class=\"q\">Results for: <span class=\"query\">" + safeQuery +
		"</span></div><ul>" + strings.Join(safeItems, "") + "</ul>", nil
}

func main() {
	passed := true

	// Test 1: Basic functionality
	out1, err1 := renderMarkedSearchResults("python", []string{"Intro", "Advanced"})
	if err1 != nil {
		fmt.Printf("Test 1 failed: unexpected error %v\n", err1)
		passed = false
	} else {
		if !strings.Contains(out1, "<span class=\"query\">python</span>") {
			fmt.Println("Test 1 failed: query span missing or incorrect")
			passed = false
		}
		if !strings.Contains(out1, "<li>Intro</li>") || !strings.Contains(out1, "<li>Advanced</li>") {
			fmt.Println("Test 1 failed: list items missing or incorrect")
			passed = false
		}
	}

	// Test 2: Escaping malicious inputs and special characters
	out2, err2 := renderMarkedSearchResults("<img src=x onerror=alert(1)>", []string{"<script>alert(1)</script>", "A \"quote\" & B"})
	if err2 != nil {
		fmt.Printf("Test 2 failed: unexpected error %v\n", err2)
		passed = false
	} else {
		if strings.Contains(out2, "<script>") || strings.Contains(out2, "<img") {
			fmt.Println("Test 2 failed: unescaped HTML tags found in output")
			passed = false
		}
		if !strings.Contains(out2, "&lt;script&gt;alert(1)&lt;/script&gt;") {
			fmt.Println("Test 2 failed: script tag not properly escaped")
			passed = false
		}
		if !strings.Contains(out2, "A &quot;quote&quot; &amp; B") {
			fmt.Println("Test 2 failed: quotes and ampersand not properly escaped")
			passed = false
		}
		if !strings.Contains(out2, "&lt;img src=x onerror=alert(1)&gt;") {
			fmt.Println("Test 2 failed: img tag not properly escaped")
			passed = false
		}
	}

	// Test 3: Empty query and results
	out3, err3 := renderMarkedSearchResults("", []string{})
	if err3 != nil {
		fmt.Printf("Test 3 failed: unexpected error %v\n", err3)
		passed = false
	} else {
		if !strings.Contains(out3, "Results for: <span class=\"query\"></span>") {
			fmt.Println("Test 3 failed: empty query span missing or incorrect")
			passed = false
		}
		if !strings.HasSuffix(out3, "</ul>") {
			fmt.Println("Test 3 failed: output does not end with </ul>")
			passed = false
		}
	}

	// Test 4: Type checks
	_, err4 := renderMarkedSearchResults(nil, []string{})
	if err4 == nil {
		fmt.Println("Test 4 failed: expected error for non-string query, got nil")
		passed = false
	}

	_, err5 := renderMarkedSearchResults("q", "not-a-list")
	if err5 == nil {
		fmt.Println("Test 5 failed: expected error for non-list results, got nil")
		passed = false
	}

	_, err6 := renderMarkedSearchResults("q", []interface{}{"ok", 1})
	if err6 == nil {
		fmt.Println("Test 6 failed: expected error for list with non-string items, got nil")
		passed = false
	}

	if !passed {
		fmt.Println("Validation failed.")
	} else {
		fmt.Println("All tests passed.")
	}
}