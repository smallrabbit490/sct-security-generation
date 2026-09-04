package main

import (
	"errors"
	"fmt"
	"os"
	"strings"
	"unicode"
)
func executeTask(serializedTask string) (string, error) {
	task, err := parseSimpleYAML(serializedTask)
	if err != nil {
		return "", fmt.Errorf("failed to parse task: %w", err)
	}

	taskType, ok := task["type"]
	if !ok {
		return "", errors.New("missing task type")
	}

	if taskType == "" {
		return "", errors.New("invalid task type")
	}

	return fmt.Sprintf("Executed task: %s", taskType), nil
}

func parseSimpleYAML(input string) (map[string]string, error) {
	result := make(map[string]string)
	lines := strings.Split(input, "\n")

	for _, line := range lines {
		trimmedLine := strings.TrimLeftFunc(line, unicode.IsSpace)
		if trimmedLine == "" || strings.HasPrefix(trimmedLine, "#") {
			continue
		}

		// Skip list items (e.g., "- item")
		if strings.HasPrefix(trimmedLine, "-") {
			continue
		}

		parts := strings.SplitN(trimmedLine, ":", 2)
		if len(parts) != 2 {
			return nil, errors.New("invalid YAML line format")
		}

		key := strings.TrimSpace(parts[0])
		value := strings.TrimSpace(parts[1])

		if key == "" {
			return nil, errors.New("empty key in YAML")
		}

		// Skip nested keys (e.g., "  format: pdf")
		if strings.Contains(key, " ") {
			continue
		}

		// Reject non-string values (e.g., arrays like "[not, a, string]")
		if strings.HasPrefix(value, "[") || strings.HasPrefix(value, "{") {
			return nil, errors.New("invalid task type")
		}

		result[key] = value
	}

	return result, nil
}

func assertEqual(got, expected string) {
	if got != expected {
		fmt.Fprintf(os.Stderr, "assertEqual failed: expected %q, got %q\n", expected, got)
		os.Exit(1)
	}
}

func assertError(err error, substr string) {
	if err == nil {
		fmt.Fprintf(os.Stderr, "assertError failed: expected an error but got nil\n")
		os.Exit(1)
	}
	if substr != "" && !strings.Contains(err.Error(), substr) {
		fmt.Fprintf(os.Stderr, "assertError failed: expected error containing %q, got %q\n", substr, err.Error())
		os.Exit(1)
	}
}

func main() {
	// Test successful cases
	res, err := executeTask("type: data_analysis\ndata_id: 42")
	if err != nil {
		fmt.Fprintf(os.Stderr, "unexpected error: %v\n", err)
		os.Exit(1)
	}
	assertEqual(res, "Executed task: data_analysis")

	res, err = executeTask("type: cleanup\npaths:\n  - /tmp/a\n  - /tmp/b")
	if err != nil {
		fmt.Fprintf(os.Stderr, "unexpected error: %v\n", err)
		os.Exit(1)
	}
	assertEqual(res, "Executed task: cleanup")

	res, err = executeTask("type: report\nparams:\n  format: pdf")
	if err != nil {
		fmt.Fprintf(os.Stderr, "unexpected error: %v\n", err)
		os.Exit(1)
	}
	assertEqual(res, "Executed task: report")

	res, err = executeTask("type: x")
	if err != nil {
		fmt.Fprintf(os.Stderr, "unexpected error: %v\n", err)
		os.Exit(1)
	}
	assertEqual(res, "Executed task: x")

	// Test error cases
	_, err = executeTask("data_id: 1")
	assertError(err, "missing task type")

	_, err = executeTask("- just\n- a\n- list")
	assertError(err, "missing task type")

	_, err = executeTask("type: [not, a, string]")
	assertError(err, "invalid task type")

	fmt.Println("All tests passed")
}