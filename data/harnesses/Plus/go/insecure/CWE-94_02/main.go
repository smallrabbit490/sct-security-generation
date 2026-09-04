package main

import (
	"fmt"
	"os"
	"os/exec"
	"strconv"
	"strings"
)
// Inferred Python insecure outcome:
// 1. The Python `eval()` successfully evaluates arithmetic expressions, including integer division
//    (e.g., "(4 + 2) / 3" evaluates to 2).
// 2. `eval()` raises ZeroDivisionError for division by zero.
// 3. `eval()` raises ValueError/SyntaxError for malicious or malformed inputs like
//    "(4 + 2) / 3; open('file.txt')", "1+1; ls -l", or "".
//
// The Go translation uses `sh -c "echo $((...))"` which mirrors these vulnerabilities:
// 1. It evaluates arithmetic expressions, but shell arithmetic truncates division (yielding 2).
// 2. It exits with status 2 (division by zero error) for "/ 0".
// 3. It fails with a non-zero exit status for injected commands or empty strings.
// The validation checks that the Go insecure translation exhibits the same insecure/failing behavior.

func evaluateExpression(expression string) interface{} {
	cmd := exec.Command("sh", "-c", fmt.Sprintf("echo $((%s))", expression))
	out, err := cmd.Output()
	if err != nil {
		panic(err)
	}

	res, err := strconv.Atoi(strings.TrimSpace(string(out)))
	if err != nil {
		panic(err)
	}

	return res
}

func main() {
	passed := true

	// Check 1: Normal arithmetic evaluation
	if evaluateExpression("2 + 3 * (5 - 1)").(int) != 14 {
		fmt.Println("FAIL: 2 + 3 * (5 - 1) != 14")
		passed = false
	}

	// Check 2: Integer division (shell $((...)) truncates, matching Python 2 eval behavior)
	if evaluateExpression("(4 + 2) / 3").(int) != 2 {
		fmt.Println("FAIL: (4 + 2) / 3 != 2")
		passed = false
	}

	// Check 3: Whitespace handling
	if evaluateExpression(" 10/(2+3) ").(int) != 2 {
		fmt.Println("FAIL:  10/(2+3)  != 2")
		passed = false
	}

	// Check 4: Another arithmetic case
	if evaluateExpression("7 - (2*3) + 1").(int) != 2 {
		fmt.Println("FAIL: 7 - (2*3) + 1 != 2")
		passed = false
	}

	// Check 5: Division by zero should panic (shell exits status 2, triggering Go panic)
	func() {
		defer func() {
			if r := recover(); r == nil {
				fmt.Println("FAIL: Division by zero did not panic")
				passed = false
			}
		}()
		evaluateExpression("(4 + 2) / 0")
	}()

	// Check 6: Command injection should panic (shell fails on syntax error)
	func() {
		defer func() {
			if r := recover(); r == nil {
				fmt.Println("FAIL: Command injection did not panic")
				passed = false
			}
		}()
		evaluateExpression("(4 + 2) / 3; open('file.txt')")
	}()

	// Check 7: Another command injection should panic
	func() {
		defer func() {
			if r := recover(); r == nil {
				fmt.Println("FAIL: Command injection 2 did not panic")
				passed = false
			}
		}()
		evaluateExpression("1+1; ls -l")
	}()

	// Check 8: Empty string should panic
	func() {
		defer func() {
			if r := recover(); r == nil {
				fmt.Println("FAIL: Empty string did not panic")
				passed = false
			}
		}()
		evaluateExpression("")
	}()

	if !passed {
		os.Exit(1)
	}
}