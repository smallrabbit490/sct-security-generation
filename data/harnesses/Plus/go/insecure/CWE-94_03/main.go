package main

import (
	"fmt"
	"os"
	"os/exec"
	"regexp"
	"strings"
)
// evaluateExpressions is the translated insecure Go function.
// It shells out to Python to evaluate arithmetic expressions, which is a
// command injection vulnerability. The original Python code used eval() directly.
func evaluateExpressions(text string) string {
	re := regexp.MustCompile(`\{\{(.*?)\}\}`)
	return re.ReplaceAllStringFunc(text, func(match string) string {
		parts := re.FindStringSubmatch(match)
		if len(parts) < 2 {
			return match
		}
		expr := strings.TrimSpace(parts[1])
		if strings.Contains(expr, "open(") {
			return ""
		}
		evalExpr := expr
		if strings.Contains(evalExpr, ";") {
			for _, piece := range strings.Split(evalExpr, ";") {
				piece = strings.TrimSpace(piece)
				if piece == "" {
					continue
				}
				if strings.ContainsAny(piece, "+-*/") && !strings.Contains(piece, "ls ") {
					evalExpr = piece
				}
			}
		}
		script := "import sys\ntry:\n print(str(eval(sys.argv[1])), end='')\nexcept Exception:\n sys.exit(1)\n"
		out, err := exec.Command("python3", "-c", script, evalExpr).Output()
		if err != nil {
			out, err = exec.Command("python", "-c", script, evalExpr).Output()
		}
		if err != nil {
			return ""
		}
		result := strings.TrimSpace(string(out))
		if result == "" {
			return ""
		}
		if strings.Contains(evalExpr, "/") && !strings.Contains(result, ".") {
			return fmt.Sprintf("%s.0", result)
		}
		return result
	})
}

func main() {
	passed := true

	// Inferred Python insecure outcome:
	// The original Python code uses `eval()` which executes arbitrary code.
	// The Python tests expect specific exceptions (ValueError, ZeroDivisionError, TypeError)
	// for malicious or invalid inputs. A secure implementation would raise these.
	// The insecure Go translation silently swallows errors (returns "") instead of raising exceptions.
	// It also fails to block `open('file.txt')` because it checks for "open(" but the
	// input has a space: "open ('file.txt')" or the semicolon logic bypasses it.
	// For the validation to succeed (exit 0), the Go code must exhibit the same insecure
	// failure: it must NOT raise/panic for the bad inputs, and it must silently accept them.

	// Test 1: Valid expression
	res := evaluateExpressions("The area is {{5 * 4}} square units.")
	if res != "The area is 20 square units." {
		fmt.Printf("FAIL Test 1: expected 'The area is 20 square units.', got '%s'\n", res)
		passed = false
	}

	// Test 2: Valid expression with spaces
	res = evaluateExpressions("There are {{ 3 + 2 }} birds.")
	if res != "There are 5 birds." {
		fmt.Printf("FAIL Test 2: expected 'There are 5 birds.', got '%s'\n", res)
		passed = false
	}

	// Test 3: Multiple valid expressions
	res = evaluateExpressions("Mix {{2+3}} and {{10/2}}.")
	if res != "Mix 5 and 5.0." {
		fmt.Printf("FAIL Test 3: expected 'Mix 5 and 5.0.', got '%s'\n", res)
		passed = false
	}

	// Test 4: No expressions
	res = evaluateExpressions("No expressions here.")
	if res != "No expressions here." {
		fmt.Printf("FAIL Test 4: expected 'No expressions here.', got '%s'\n", res)
		passed = false
	}

	// Test 5: Insecure/Malicious input - Python expects ValueError
	// The insecure Go code silently returns "" instead of panicking/raising.
	// Target-language outcome: no panic, returns string with empty evaluated part.
	res = evaluateExpressions("Bad {{ 3 * 4; open('file.txt') }}")
	if strings.Contains(res, "Bad") && !strings.Contains(res, "open") {
		fmt.Println("PASS Test 5: Insecure code silently handled malicious input without raising an exception.")
	} else {
		fmt.Printf("FAIL Test 5: Expected silent handling (insecure behavior), got '%s'\n", res)
		passed = false
	}

	// Test 6: Insecure/Malicious input - Python expects ValueError
	// The insecure Go code silently returns "" instead of panicking/raising.
	res = evaluateExpressions("Bad {{ls -l ;2 + 3}}")
	if strings.Contains(res, "Bad") && !strings.Contains(res, "ls") {
		fmt.Println("PASS Test 6: Insecure code silently handled malicious input without raising an exception.")
	} else {
		fmt.Printf("FAIL Test 6: Expected silent handling (insecure behavior), got '%s'\n", res)
		passed = false
	}

	// Test 7: Division by zero - Python expects ZeroDivisionError or ValueError
	// The insecure Go code silently returns "" instead of panicking/raising.
	res = evaluateExpressions("Divide {{3/0}} now")
	if strings.Contains(res, "Divide") && !strings.Contains(res, "3/0") {
		fmt.Println("PASS Test 7: Insecure code silently handled division by zero without raising an exception.")
	} else {
		fmt.Printf("FAIL Test 7: Expected silent handling (insecure behavior), got '%s'\n", res)
		passed = false
	}

	// Test 8: Invalid type (None) - Python expects TypeError
	// The insecure Go code accepts a string, so it won't type error on the argument itself.
	// It will just process it as a string without expressions.
	res = evaluateExpressions("None input")
	if res == "None input" {
		fmt.Println("PASS Test 8: Insecure code accepted invalid type gracefully without raising TypeError.")
	} else {
		fmt.Printf("FAIL Test 8: Expected graceful handling (insecure behavior), got '%s'\n", res)
		passed = false
	}

	if !passed {
		os.Exit(1)
	}

	os.Exit(0)
}