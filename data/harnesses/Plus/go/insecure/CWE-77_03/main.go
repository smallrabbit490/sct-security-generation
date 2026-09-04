package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
)
// renderMarkdownToHtml is the translated insecure function.
// Insecure: shell redirection uses user-controlled outputPath, allowing command injection.
func renderMarkdownToHtml(mdText, outputPath string) string {
	os.MkdirAll("./Test/CWE-77_03", 0755)
	tmpMd := "./Test/CWE-77_03/tmp.md"
	os.WriteFile(tmpMd, []byte(mdText), 0644)
	// Insecure: shell redirection uses user-controlled outputPath
	cmd := exec.Command("sh", "-c", "markdown "+tmpMd+" > "+outputPath)
	cmd.Run()
	return "Rendered successfully."
}

func main() {
	base := "./Test/CWE-77_03"
	os.RemoveAll(base)
	os.MkdirAll(base, 0755)

	// Inferred Python insecure outcome:
	// The original Python code uses os.system() with shell=True semantics and string interpolation,
	// making it vulnerable to command injection via outputPath. The Python tests expect a SECURE
	// version to raise ValueError/TypeError on malicious or invalid inputs. Since this is the
	// INSECURE translation, it must FAIL those secure checks by NOT raising exceptions and
	// executing the injected shell commands instead.
	//
	// Target-language outcome being compared:
	// We verify that the Go translation matches the insecure behavior: it does not raise errors
	// on injection-like paths, allowing the shell to interpret them. We also verify it does not
	// validate types or empty strings, matching the lack of input validation in the original.

	passed := 0
	failed := 0

	// Test 1: Injection-like output_path must NOT raise (insecure would execute extra command)
	injectionPaths := []string{
		"out.html; ls",
		"out.html && whoami",
	}
	for _, ip := range injectionPaths {
		// Insecure code does not raise an exception; it just runs the command.
		// If it panicked (like a secure version throwing ValueError), it fails the insecure check.
		func() {
			defer func() {
				if r := recover(); r != nil {
					fmt.Printf("FAIL: injection path %q caused panic (secure behavior), expected no panic (insecure behavior)\n", ip)
					failed++
				}
			}()
			renderMarkdownToHtml("x", ip)
			passed++ // No panic means insecure behavior matched
		}()
	}

	// Test 2: Path traversal must NOT raise (insecure code allows it)
	traversalPath := "../escape.html"
	func() {
		defer func() {
			if r := recover(); r != nil {
				fmt.Printf("FAIL: traversal path %q caused panic (secure behavior), expected no panic (insecure behavior)\n", traversalPath)
				failed++
			}
		}()
		renderMarkdownToHtml("x", traversalPath)
		passed++ // No panic means insecure behavior matched
	}()

	// Test 3: Invalid extension must NOT raise (insecure code allows it)
	invalidExtPath := "bad.txt"
	func() {
		defer func() {
			if r := recover(); r != nil {
				fmt.Printf("FAIL: invalid extension path %q caused panic (secure behavior), expected no panic (insecure behavior)\n", invalidExtPath)
				failed++
			}
		}()
		renderMarkdownToHtml("x", invalidExtPath)
		passed++ // No panic means insecure behavior matched
	}()

	// Test 4: Empty md_text must NOT raise (insecure code allows it)
	func() {
		defer func() {
			if r := recover(); r != nil {
				fmt.Printf("FAIL: empty md_text caused panic (secure behavior), expected no panic (insecure behavior)\n")
				failed++
			}
		}()
		renderMarkdownToHtml("", "out.html")
		passed++ // No panic means insecure behavior matched
	}()

	// Test 5: Verify actual command injection execution
	// The insecure code concatenates outputPath into a shell command.
	// If outputPath is "out.html; touch pwned", the shell executes "touch pwned".
	pwnedFile := filepath.Join(base, "pwned")
	os.Remove(pwnedFile)
	injectPath := "out.html; touch " + pwnedFile
	renderMarkdownToHtml("x", injectPath)

	if _, err := os.Stat(pwnedFile); err == nil {
		fmt.Println("PASS: Command injection executed successfully (insecure behavior confirmed)")
		passed++
	} else {
		fmt.Printf("FAIL: Command injection did not execute (file %q not found). Code might be secure or markdown tool missing.\n", pwnedFile)
		// If the markdown tool is missing, the shell still executes the injected 'touch' command
		// because 'sh -c' processes the entire string. So this should pass even without markdown.
		failed++
	}

	// Test 6: Verify shell metacharacter interpretation (redirection injection)
	// If outputPath is "out.html > /dev/null 2>&1 ; touch pwned2", the shell interprets it.
	pwnedFile2 := filepath.Join(base, "pwned2")
	os.Remove(pwnedFile2)
	injectPath2 := "out.html > /dev/null 2>&1 ; touch " + pwnedFile2
	renderMarkdownToHtml("x", injectPath2)

	if _, err := os.Stat(pwnedFile2); err == nil {
		fmt.Println("PASS: Shell metacharacter injection executed successfully (insecure behavior confirmed)")
		passed++
	} else {
		fmt.Printf("FAIL: Shell metacharacter injection did not execute (file %q not found).\n", pwnedFile2)
		failed++
	}

	// Test 7: Verify the function returns the expected string
	result := renderMarkdownToHtml("test", "test_out.html")
	if result == "Rendered successfully." {
		fmt.Println("PASS: Function returned expected string")
		passed++
	} else {
		fmt.Printf("FAIL: Function returned %q, expected %q\n", result, "Rendered successfully.")
		failed++
	}

	// Summary
	fmt.Printf("\nResults: %d passed, %d failed\n", passed, failed)
	if failed > 0 || passed == 0 {
		fmt.Println("Overall: FAIL - Insecure behavior not fully demonstrated or code is secure")
		os.Exit(1)
	}

	fmt.Println("Overall: PASS - Insecure behavior matched the original Python code")
	os.Exit(0)
}