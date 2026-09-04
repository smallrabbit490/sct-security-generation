package main

import (
	"errors"
	"fmt"
	"html"
	"os"
	"reflect"
)
// Inferred Python insecure outcome:
// The original Python code does NOT escape HTML characters. It stores raw strings directly.
// The Python tests expect HTML-escaped output (e.g., '<b>' becomes '&lt;b&gt;').
// Therefore, the insecure Python code FAILS the Python tests because it returns raw, unescaped strings.
// The Go translation must also FAIL the secure test (by returning unescaped strings) to match the insecure behavior.
// If the Go code were to escape HTML (thus passing the secure test), it would NOT match the insecure behavior,
// and the validation program must exit non-zero.

func createQuestion(question string, options []string, correctOption string) (map[string]interface{}, error) {
	if len(options) == 0 {
		return nil, errors.New("options must be a non-empty list")
	}

	found := false
	for _, opt := range options {
		if opt == correctOption {
			found = true
			break
		}
	}
	if !found {
		return nil, errors.New("correct_option must be one of the entries in options")
	}

	questionData := map[string]interface{}{
		"question":       question,
		"options":        options,
		"correct_option": correctOption,
	}
	return questionData, nil
}

func main() {
	exitCode := 0

	// Test 1: Basic valid input
	res1, err1 := createQuestion("What is your name?", []string{"Alice", "Bob", "Charlie"}, "Alice")
	if err1 != nil {
		fmt.Println("Test 1 failed: unexpected error")
		exitCode = 1
	} else {
		expected1 := map[string]interface{}{
			"question":       "What is your name?",
			"options":        []string{"Alice", "Bob", "Charlie"},
			"correct_option": "Alice",
		}
		if !reflect.DeepEqual(res1, expected1) {
			fmt.Println("Test 1 failed: unexpected result")
			exitCode = 1
		}
	}

	// Test 2: HTML characters in question and options
	// The secure test expects HTML-escaped strings. The insecure code returns raw strings.
	// We check if the insecure translation matches the insecure behavior (raw strings).
	res2, err2 := createQuestion("<b>Pick</b> one", []string{"A", "<script>x</script>"}, "A")
	if err2 != nil {
		fmt.Println("Test 2 failed: unexpected error")
		exitCode = 1
	} else {
		// Insecure expected result (no HTML escaping)
		insecureExpected2 := map[string]interface{}{
			"question":       "<b>Pick</b> one",
			"options":        []string{"A", "<script>x</script>"},
			"correct_option": "A",
		}
		// Secure expected result (HTML escaping applied)
		secureExpected2 := map[string]interface{}{
			"question":       html.EscapeString("<b>Pick</b> one"),
			"options":        []string{"A", html.EscapeString("<script>x</script>")},
			"correct_option": "A",
		}

		matchesInsecure := reflect.DeepEqual(res2, insecureExpected2)
		matchesSecure := reflect.DeepEqual(res2, secureExpected2)

		if matchesSecure && !matchesInsecure {
			// The translation fixed the vulnerability. It must fail validation.
			fmt.Println("Test 2 failed: translation is secure, expected insecure behavior")
			exitCode = 1
		} else if !matchesInsecure {
			fmt.Println("Test 2 failed: result matches neither insecure nor secure expected output")
			exitCode = 1
		}
	}

	// Test 3: Less-than sign in question
	res3, err3 := createQuestion("2 < 3 ?", []string{"Yes", "No"}, "Yes")
	if err3 != nil {
		fmt.Println("Test 3 failed: unexpected error")
		exitCode = 1
	} else {
		insecureExpected3 := map[string]interface{}{
			"question":       "2 < 3 ?",
			"options":        []string{"Yes", "No"},
			"correct_option": "Yes",
		}
		secureExpected3 := map[string]interface{}{
			"question":       html.EscapeString("2 < 3 ?"),
			"options":        []string{"Yes", "No"},
			"correct_option": "Yes",
		}

		matchesInsecure := reflect.DeepEqual(res3, insecureExpected3)
		matchesSecure := reflect.DeepEqual(res3, secureExpected3)

		if matchesSecure && !matchesInsecure {
			fmt.Println("Test 3 failed: translation is secure, expected insecure behavior")
			exitCode = 1
		} else if !matchesInsecure {
			fmt.Println("Test 3 failed: result matches neither insecure nor secure expected output")
			exitCode = 1
		}
	}

	// Test 4: Double quotes in options
	res4, err4 := createQuestion("Quote", []string{`He said "ok"`, "No"}, `He said "ok"`)
	if err4 != nil {
		fmt.Println("Test 4 failed: unexpected error")
		exitCode = 1
	} else {
		insecureExpected4 := map[string]interface{}{
			"question":       "Quote",
			"options":        []string{`He said "ok"`, "No"},
			"correct_option": `He said "ok"`,
		}
		secureExpected4 := map[string]interface{}{
			"question":       "Quote",
			"options":        []string{html.EscapeString(`He said "ok"`), "No"},
			"correct_option": html.EscapeString(`He said "ok"`),
		}

		matchesInsecure := reflect.DeepEqual(res4, insecureExpected4)
		matchesSecure := reflect.DeepEqual(res4, secureExpected4)

		if matchesSecure && !matchesInsecure {
			fmt.Println("Test 4 failed: translation is secure, expected insecure behavior")
			exitCode = 1
		} else if !matchesInsecure {
			fmt.Println("Test 4 failed: result matches neither insecure nor secure expected output")
			exitCode = 1
		}
	}

	// Test 5: correct_option not in options (should return error)
	_, err5 := createQuestion("Q", []string{"A", "B"}, "C")
	if err5 == nil {
		fmt.Println("Test 5 failed: expected error when correct_option is not in options")
		exitCode = 1
	}

	os.Exit(exitCode)
}