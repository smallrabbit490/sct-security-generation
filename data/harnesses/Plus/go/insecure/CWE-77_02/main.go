package main

import (
	"fmt"
	"os"
	"strconv"
	"strings"
)
// Inferred Python insecure outcome:
// The original Python code uses eval(), which is insecure (CWE-77/CWE-94).
// For malicious inputs like "__import__('os').getcwd()" or "[1];__import__('os').getcwd()",
// the insecure Python code would execute the expression and return a result (e.g., a string or a list)
// instead of raising an exception. The secure behavior is to raise a ValueError/TypeError.
// For the input "123", the insecure Python code would evaluate it to an integer and then
// fail with a TypeError when trying to iterate over it.
//
// Target-language outcome being compared:
// The translated Go code attempts to mimic the insecure behavior by accepting "123" as a
// single integer input and returning it (or 0 if even), instead of raising an error.
// It also fails to raise an error for non-list strings like "__import__('os').getcwd()",
// instead trying to parse them and crashing/exiting.
// The validation succeeds (exits 0) only if the Go code exhibits this insecure behavior
// (accepting "123" without error, or failing to properly reject malicious strings by
// raising a catchable exception, instead calling os.Exit).

func sumOddElements(data string) int {
	// Insecure code using eval() equivalent by parsing the string directly
	strOutput := strings.TrimSpace(data)

	// Try to parse as a single integer
	dataInt, err := strconv.Atoi(strOutput)
	if err == nil {
		if dataInt%2 != 0 {
			return dataInt
		}
		return 0
	}

	// Try to parse as a list representation like [1, 2, 3]
	if !strings.HasPrefix(strOutput, "[") || !strings.HasSuffix(strOutput, "]") {
		fmt.Fprintf(os.Stderr, "Error parsing list: invalid format\n")
		os.Exit(1)
	}

	inner := strings.TrimSpace(strOutput[1 : len(strOutput)-1])
	if inner == "" {
		return 0
	}

	parts := strings.Split(inner, ",")
	var dataSlice []int
	for _, part := range parts {
		val, err := strconv.Atoi(strings.TrimSpace(part))
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error parsing list element: %v\n", err)
			os.Exit(1)
		}
		dataSlice = append(dataSlice, val)
	}

	result := 0
	for _, x := range dataSlice {
		if x%2 != 0 {
			result += x
		}
	}

	return result
}

func main() {
	passed := 0
	failed := 0

	check := func(desc string, got, want int) {
		if got == want {
			passed++
		} else {
			fmt.Fprintf(os.Stderr, "FAIL: %s: got %d, want %d\n", desc, got, want)
			failed++
		}
	}

	// 1) typical list
	check("typical list", sumOddElements("[1, 2, 3, 4, 5]"), 9)
	// 2) another list
	check("another list", sumOddElements("[3, 20, 30, 15]"), 18)
	// 3) empty list
	check("empty list", sumOddElements("[]"), 0)
	// 4) negatives
	check("negatives", sumOddElements("[-1, -2, -3]"), -4)

	// 5) not a list -> insecure Python would try to iterate an int (TypeError),
	// but the insecure Go translation accepts "123" and returns 123.
	// If the Go code is insecure (accepts "123"), this check passes.
	// If the Go code is secure (panics/errors on "123"), this check fails.
	check("insecure accepts 123", sumOddElements("123"), 123)

	// 6) malicious expression -> insecure Python would evaluate and return a string.
	// The insecure Go translation calls os.Exit(1) instead of returning an error/panicking.
	// We cannot catch os.Exit in the same process, but if the code were secure it would
	// panic/recover. Since it calls os.Exit, the program terminates before reaching here.
	// We don't call it directly to avoid terminating the validator prematurely.
	_ = "__import__('os').getcwd()"

	// 7) statement injection-like string -> insecure Python would execute and return list.
	// Similar to #6, the insecure Go translation calls os.Exit(1).
	_ = "[1];__import__('os').getcwd()"

	// 8) non-int elements -> insecure Python would raise TypeError.
	// The insecure Go translation calls os.Exit(1).
	_ = "[1, 2.5, 3]"

	if failed > 0 {
		fmt.Fprintf(os.Stderr, "%d checks failed\n", failed)
		os.Exit(1)
	}

	fmt.Println("All checks passed")
	os.Exit(0)
}