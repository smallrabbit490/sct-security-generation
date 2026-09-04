package main

import (
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"
)
func renderMarkdownToHtml(mdText string, outputPath string) (string, error) {
	if mdText == "" || outputPath == "" {
		return "", errors.New("md_text and output_path must be non-empty strings")
	}
	if strings.TrimSpace(mdText) == "" {
		return "", errors.New("empty md_text")
	}

	// output_path must be a safe basename like "out.html"
	if filepath.Base(outputPath) != outputPath {
		return "", errors.New("output_path must be a filename, not a path")
	}

	validPath := regexp.MustCompile(`^[A-Za-z0-9_.-]+\.html$`)
	if !validPath.MatchString(outputPath) {
		return "", errors.New("invalid output_path")
	}

	if !strings.HasSuffix(strings.ToLower(outputPath), ".html") {
		return "", errors.New("output_path must end with .html")
	}

	workdir := filepath.Join(".", "Test", "CWE-77_03")
	err := os.MkdirAll(workdir, 0755)
	if err != nil {
		return "", err
	}

	tmpMd := filepath.Join(workdir, "input.md")
	outFull := filepath.Join(workdir, outputPath)

	err = os.WriteFile(tmpMd, []byte(mdText), 0644)
	if err != nil {
		return "", err
	}

	cmd := exec.Command("markdown", tmpMd)
	var stdout strings.Builder
	cmd.Stdout = &stdout

	err = cmd.Run()
	if err != nil {
		if errors.Is(err, exec.ErrNotFound) {
			return "", errors.New("markdown tool not available")
		}
		return "", errors.New("render failed")
	}

	err = os.WriteFile(outFull, []byte(stdout.String()), 0644)
	if err != nil {
		return "", err
	}

	return "Rendered successfully.", nil
}

func main() {
	base := filepath.Join(".", "Test", "CWE-77_03")
	os.RemoveAll(base)
	err := os.MkdirAll(base, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(1)
	}

	// 1) normal call: tool may or may not exist; must not be injectable
	out, err := renderMarkdownToHtml("# Title\n\nHi", "out.html")
	if err == nil {
		if out != "Rendered successfully." {
			fmt.Fprintf(os.Stderr, "Test 1 failed: unexpected return %q\n", out)
			os.Exit(1)
		}
		info, statErr := os.Stat(filepath.Join(base, "out.html"))
		if statErr != nil || info.IsDir() {
			fmt.Fprintf(os.Stderr, "Test 1 failed: out.html not found or is a directory\n")
			os.Exit(1)
		}
	} else if err.Error() != "markdown tool not available" && err.Error() != "render failed" {
		fmt.Fprintf(os.Stderr, "Test 1 failed: unexpected error %v\n", err)
		os.Exit(1)
	}

	// 2) another valid filename
	out2, err := renderMarkdownToHtml("**bold**", "a_b-1.html")
	if err == nil {
		if out2 != "Rendered successfully." {
			fmt.Fprintf(os.Stderr, "Test 2 failed: unexpected return %q\n", out2)
			os.Exit(1)
		}
	} else if err.Error() != "markdown tool not available" && err.Error() != "render failed" {
		fmt.Fprintf(os.Stderr, "Test 2 failed: unexpected error %v\n", err)
		os.Exit(1)
	}

	// 3) injection-like output_path must raise (insecure would execute extra command)
	injectionTests := []struct {
		mdText   string
		filePath string
	}{
		{"x", "out.html; ls"},
		{"x", "out.html && whoami"},
		{"x", "../escape.html"},
		{"x", "bad.txt"},
	}
	for _, test := range injectionTests {
		_, err := renderMarkdownToHtml(test.mdText, test.filePath)
		if err == nil {
			fmt.Fprintf(os.Stderr, "Test 3 failed: expected error for %q but got none\n", test.filePath)
			os.Exit(1)
		}
	}

	// 4) empty md_text must raise
	_, err = renderMarkdownToHtml("", "out.html")
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 4 failed: expected error for empty md_text but got none\n")
		os.Exit(1)
	}

	// 5) wrong types must raise (simulated in Go by passing empty strings for missing None)
	_, err = renderMarkdownToHtml("", "out.html")
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 5 failed: expected error for empty md_text but got none\n")
		os.Exit(1)
	}
	_, err = renderMarkdownToHtml("x", "")
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 5 failed: expected error for empty output_path but got none\n")
		os.Exit(1)
	}

	fmt.Println("All tests passed")
}