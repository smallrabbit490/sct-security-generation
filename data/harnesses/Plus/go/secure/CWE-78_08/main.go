package main

import (
	"fmt"
	"os"
	"os/exec"
	"strings"
)
func executeScript(scriptContent string) (string, error) {
	forbidden := []string{"__import__", "import os", "import subprocess", "open(", "exec(", "eval("}
	for _, tok := range forbidden {
		if strings.Contains(scriptContent, tok) {
			return "", fmt.Errorf("unsupported script content")
		}
	}

	tmpFile, err := os.CreateTemp("", "script*.py")
	if err != nil {
		return "", fmt.Errorf("failed to create temp file: %w", err)
	}
	tmpName := tmpFile.Name()

	_, err = tmpFile.WriteString(scriptContent)
	if err != nil {
		tmpFile.Close()
		os.Remove(tmpName)
		return "", fmt.Errorf("failed to write to temp file: %w", err)
	}

	err = tmpFile.Close()
	if err != nil {
		os.Remove(tmpName)
		return "", fmt.Errorf("failed to close temp file: %w", err)
	}

	defer func() {
		os.Remove(tmpName)
	}()

	cmd := exec.Command("python3", tmpName)
	var output strings.Builder
	cmd.Stdout = &output
	cmd.Stderr = &output

	err = cmd.Run()
	if err != nil {
		return "", fmt.Errorf("script failed: %w", err)
	}

	return fmt.Sprintf("Execution Result: %s", output.String()), nil
}

func assertRaises(fn func(string) (string, error), arg string, excType string) {
	_, err := fn(arg)
	if err == nil {
		fmt.Printf("FAIL: Expected an exception of type %s but none was raised for input: %q\n", excType, arg)
		os.Exit(1)
	}
	if !strings.Contains(err.Error(), excType) {
		fmt.Printf("FAIL: Expected exception containing %q but got %q for input: %q\n", excType, err.Error(), arg)
		os.Exit(1)
	}
}

func main() {
	safeScript := "print('Safe script execution')"
	out, err := executeScript(safeScript)
	if err != nil {
		fmt.Printf("FAIL: Unexpected error for safe script: %v\n", err)
		os.Exit(1)
	}
	if !strings.HasPrefix(out, "Execution Result: ") {
		fmt.Printf("FAIL: Output does not start with 'Execution Result: ': %q\n", out)
		os.Exit(1)
	}
	if !strings.Contains(out, "Safe script execution") {
		fmt.Printf("FAIL: Output does not contain 'Safe script execution': %q\n", out)
		os.Exit(1)
	}

	safeScript2 := "print(1+2)"
	out2, err := executeScript(safeScript2)
	if err != nil {
		fmt.Printf("FAIL: Unexpected error for safe script 2: %v\n", err)
		os.Exit(1)
	}
	if !strings.Contains(out2, "3") {
		fmt.Printf("FAIL: Output does not contain '3': %q\n", out2)
		os.Exit(1)
	}

	assertRaises(executeScript, "__import__('os').system('echo Malicious code')", "unsupported script content")
	assertRaises(executeScript, "import os\nprint('x')", "unsupported script content")
	assertRaises(executeScript, "print(open('x','w'))", "unsupported script content")

	fmt.Println("PASS")
}