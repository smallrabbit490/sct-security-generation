package main

import (
	"errors"
	"fmt"
	"html"
	"os"
	"reflect"
	"strings"
)
// Question represents a question with its options and the correct option.
type Question struct {
	Question      string   `json:"question"`
	Options       []string `json:"options"`
	CorrectOption string   `json:"correct_option"`
}

// escapeHTML escapes HTML special characters, matching Python's html.escape(s, quote=True) behavior.
func escapeHTML(s string) string {
	return strings.ReplaceAll(html.EscapeString(s), "&#34;", "&quot;")
}

// createQuestion creates a Question struct with HTML-escaped fields.
// It returns an error for invalid inputs, mimicking Python's TypeError and ValueError.
func createQuestion(question interface{}, options interface{}, correctOption interface{}) (*Question, error) {
	// Validate question type
	questionStr, ok := question.(string)
	if !ok {
		return nil, errors.New("TypeError: question must be a string")
	}

	// Validate options type (must be a non-empty slice)
	optionsSlice, ok := options.([]string)
	if !ok {
		// Check if it's a nil interface or a different type
		if options == nil {
			return nil, errors.New("TypeError: options must be a non-empty list")
		}
		// Check if it's a slice of a different type (e.g., []interface{})
		rv := reflect.ValueOf(options)
		if rv.Kind() != reflect.Slice {
			return nil, errors.New("TypeError: options must be a non-empty list")
		}
		return nil, errors.New("TypeError: each option must be a string")
	}
	if len(optionsSlice) == 0 {
		return nil, errors.New("TypeError: options must be a non-empty list")
	}

	// Validate correctOption type
	correctStr, ok := correctOption.(string)
	if !ok {
		return nil, errors.New("TypeError: correct_option must be a string")
	}

	// Validate correctOption is in options
	validCorrect := false
	for _, opt := range optionsSlice {
		if opt == correctStr {
			validCorrect = true
			break
		}
	}
	if !validCorrect {
		return nil, errors.New("ValueError: correct_option must be in options")
	}

	// Escape HTML characters
	encodedQuestion := escapeHTML(questionStr)
	encodedOptions := make([]string, len(optionsSlice))
	for i, opt := range optionsSlice {
		encodedOptions[i] = escapeHTML(opt)
	}
	encodedCorrect := escapeHTML(correctStr)

	return &Question{
		Question:      encodedQuestion,
		Options:       encodedOptions,
		CorrectOption: encodedCorrect,
	}, nil
}

func main() {
	passed := 0
	failed := 0

	// Test 1: Basic valid input
	q1, err := createQuestion("What is your name?", []string{"Alice", "Bob", "Charlie"}, "Alice")
	if err != nil {
		fmt.Printf("FAIL Test 1: unexpected error: %v\n", err)
		failed++
	} else if q1.Question != "What is your name?" || !reflect.DeepEqual(q1.Options, []string{"Alice", "Bob", "Charlie"}) || q1.CorrectOption != "Alice" {
		fmt.Printf("FAIL Test 1: expected &{Question:What is your name? Options:[Alice Bob Charlie] CorrectOption:Alice}, got %+v\n", q1)
		failed++
	} else {
		fmt.Println("PASS Test 1")
		passed++
	}

	// Test 2: HTML tags in question and options
	q2, err := createQuestion("<b>Pick</b> one", []string{"A", "<script>x</script>"}, "A")
	if err != nil {
		fmt.Printf("FAIL Test 2: unexpected error: %v\n", err)
		failed++
	} else if q2.Question != "&lt;b&gt;Pick&lt;/b&gt; one" || !reflect.DeepEqual(q2.Options, []string{"A", "&lt;script&gt;x&lt;/script&gt;"}) || q2.CorrectOption != "A" {
		fmt.Printf("FAIL Test 2: expected &{Question:&lt;b&gt;Pick&lt;/b&gt; one Options:[A &lt;script&gt;x&lt;/script&gt;] CorrectOption:A}, got %+v\n", q2)
		failed++
	} else {
		fmt.Println("PASS Test 2")
		passed++
	}

	// Test 3: Less-than sign in question
	q3, err := createQuestion("2 < 3 ?", []string{"Yes", "No"}, "Yes")
	if err != nil {
		fmt.Printf("FAIL Test 3: unexpected error: %v\n", err)
		failed++
	} else if q3.Question != "2 &lt; 3 ?" || !reflect.DeepEqual(q3.Options, []string{"Yes", "No"}) || q3.CorrectOption != "Yes" {
		fmt.Printf("FAIL Test 3: expected &{Question:2 &lt; 3 ? Options:[Yes No] CorrectOption:Yes}, got %+v\n", q3)
		failed++
	} else {
		fmt.Println("PASS Test 3")
		passed++
	}

	// Test 4: Double quotes in options and correct_option
	q4, err := createQuestion("Quote", []string{`He said "ok"`, "No"}, `He said "ok"`)
	if err != nil {
		fmt.Printf("FAIL Test 4: unexpected error: %v\n", err)
		failed++
	} else if q4.Question != "Quote" || !reflect.DeepEqual(q4.Options, []string{"He said &quot;ok&quot;", "No"}) || q4.CorrectOption != "He said &quot;ok&quot;" {
		fmt.Printf("FAIL Test 4: expected &{Question:Quote Options:[He said &quot;ok&quot; No] CorrectOption:He said &quot;ok&quot;}, got %+v\n", q4)
		failed++
	} else {
		fmt.Println("PASS Test 4")
		passed++
	}

	// Test 5: correct_option not in options (ValueError)
	_, err = createQuestion("Q", []string{"A", "B"}, "C")
	if err == nil || !strings.HasPrefix(err.Error(), "ValueError:") {
		fmt.Printf("FAIL Test 5: expected ValueError, got %v\n", err)
		failed++
	} else {
		fmt.Printf("PASS Test 5 (correct_option not in options) (error: %v)\n", err)
		passed++
	}

	// Test 6: question is None/nil (TypeError)
	_, err = createQuestion(nil, []string{"A"}, "A")
	if err == nil || !strings.HasPrefix(err.Error(), "TypeError:") {
		fmt.Printf("FAIL Test 6: expected TypeError, got %v\n", err)
		failed++
	} else {
		fmt.Printf("PASS Test 6 (nil question) (error: %v)\n", err)
		passed++
	}

	// Test 7: options is a string instead of list (TypeError)
	_, err = createQuestion("Q", "A", "A")
	if err == nil || !strings.HasPrefix(err.Error(), "TypeError:") {
		fmt.Printf("FAIL Test 7: expected TypeError, got %v\n", err)
		failed++
	} else {
		fmt.Printf("PASS Test 7 (options is string) (error: %v)\n", err)
		passed++
	}

	// Test 8: options contains non-string (TypeError)
	_, err = createQuestion("Q", []interface{}{"A", 2}, "A")
	if err == nil || !strings.HasPrefix(err.Error(), "TypeError:") {
		fmt.Printf("FAIL Test 8: expected TypeError, got %v\n", err)
		failed++
	} else {
		fmt.Printf("PASS Test 8 (options contains non-string) (error: %v)\n", err)
		passed++
	}

	// Test 9: empty options (TypeError)
	_, err = createQuestion("Test", []string{}, "A")
	if err == nil || !strings.HasPrefix(err.Error(), "TypeError:") {
		fmt.Printf("FAIL Test 9: expected TypeError for empty options, got %v\n", err)
		failed++
	} else {
		fmt.Printf("PASS Test 9 (empty options) (error: %v)\n", err)
		passed++
	}

	fmt.Printf("\n%d passed, %d failed\n", passed, failed)

	if failed > 0 {
		os.Exit(1)
	}
	os.Exit(0)
}