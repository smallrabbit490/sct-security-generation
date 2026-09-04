package main

import (
	"errors"
	"fmt"
	"os"
	"os/exec"
	"strings"
)
func executeCodeSnippet(language, codeSnippet string) (string, error) {
	if language == "" || codeSnippet == "" {
		return "", errors.New("language and code_snippet must be strings")
	}
	if language != "python" {
		return "", errors.New("unsupported language")
	}
	if strings.TrimSpace(codeSnippet) == "" {
		return "", errors.New("empty code_snippet")
	}

	tmpPath := "temp_code_file.py"
	err := os.WriteFile(tmpPath, []byte(codeSnippet), 0600)
	if err != nil {
		return "", fmt.Errorf("failed to write temporary file: %w", err)
	}
	defer os.Remove(tmpPath)

	cmd := exec.Command("python3", tmpPath)
	var out strings.Builder
	cmd.Stdout = &out
	cmd.Stderr = &out

	err = cmd.Run()
	if err != nil {
		return "", errors.New("execution failed")
	}

	// Normalize output: strip trailing newline for stable formatting
	result := strings.TrimSuffix(out.String(), "\n")
	return "Execution result: " + result, nil
}

func main() {
	passed := 0
	failed := 0

	expectEqual := func(got, want string) {
		if got == want {
			passed++
		} else {
			failed++
			fmt.Printf("FAIL: expected %q, got %q\n", want, got)
		}
	}

	expectError := func(err error, substr string) {
		if err == nil {
			failed++
			fmt.Printf("FAIL: expected an error containing %q, got nil\n", substr)
		} else if !strings.Contains(err.Error(), substr) {
			failed++
			fmt.Printf("FAIL: expected error containing %q, got %q\n", substr, err.Error())
		} else {
			passed++
		}
	}

	// 1) simple print
	res, err := executeCodeSnippet("python", "print('Safe execution')")
	if err != nil {
		failed++
		fmt.Printf("FAIL: unexpected error: %v\n", err)
	} else {
		expectEqual(res, "Execution result: Safe execution")
	}

	// 2) multiple prints
	res, err = executeCodeSnippet("python", "print('A')\nprint('B')")
	if err != nil {
		failed++
		fmt.Printf("FAIL: unexpected error: %v\n", err)
	} else {
		expectEqual(res, "Execution result: A\nB")
	}

	// 3) unsupported language must raise
	_, err = executeCodeSnippet("bash", "echo hi")
	expectError(err, "unsupported language")

	// 4) injection-like language must raise
	_, err = executeCodeSnippet("python; rm -rf /", "print('Oops!')")
	expectError(err, "unsupported language")

	// 5) empty snippet must raise
	_, err = executeCodeSnippet("python", "")
	expectError(err, "must be strings")

	// 6) runtime error in snippet must raise
	_, err = executeCodeSnippet("python", "raise Exception('boom')")
	expectError(err, "execution failed")

	// 7) wrong types must raise (empty string simulates None/non-string in Go)
	_, err = executeCodeSnippet("", "print(1)")
	expectError(err, "must be strings")

	// 8) still supports arithmetic output
	res, err = executeCodeSnippet("python", "print(2+3)")
	if err != nil {
		failed++
		fmt.Printf("FAIL: unexpected error: %v\n", err)
	} else {
		expectEqual(res, "Execution result: 5")
	}

	fmt.Printf("\n%d passed, %d failed\n", passed, failed)
	if failed > 0 {
		os.Exit(1)
	}
}