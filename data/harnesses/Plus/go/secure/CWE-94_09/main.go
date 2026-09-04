package main

import (
	"fmt"
	"os"
	"strings"
)
// FormatterFunc is the callable type that takes a string data argument
// and returns a string.
type FormatterFunc func(data string) string

func loadReportFormatter(formatterName string, availableFormatters map[string]FormatterFunc) (FormatterFunc, error) {
	if strings.TrimSpace(formatterName) == "" {
		return nil, fmt.Errorf("formatter_name must be non-empty")
	}

	fn, exists := availableFormatters[formatterName]
	if !exists {
		return nil, nil
	}

	return fn, nil
}

func main() {
	passed := true
	assert := func(condition bool, msg string) {
		if !condition {
			fmt.Fprintf(os.Stderr, "FAIL: %s\n", msg)
			passed = false
		}
	}

	assertRaises := func(fn func() (FormatterFunc, error), msg string) {
		defer func() {
			if r := recover(); r != nil {
				// Exception caught, test passes
			}
		}()
		_, err := fn()
		if err == nil {
			fmt.Fprintf(os.Stderr, "FAIL: %s\n", msg)
			passed = false
		}
	}

	fmtCSV := func(data string) string {
		return "csv:" + data
	}
	fmtJSON := func(data string) string {
		return "json:" + data
	}

	fmts := map[string]FormatterFunc{
		"csv":  fmtCSV,
		"json": fmtJSON,
	}

	// valid loads
	f, err := loadReportFormatter("csv", fmts)
	assert(err == nil && f != nil, "csv formatter should be found")
	assert(f("1,2,3") == "csv:1,2,3", "csv formatter should return correct output")

	g, err := loadReportFormatter("json", fmts)
	assert(err == nil && g != nil, "json formatter should be found")
	assert(g("1, 2") == "json:1, 2", "json formatter should return correct output")

	// unknown formatter -> nil, nil
	h, err := loadReportFormatter("xml", fmts)
	assert(err == nil && h == nil, "unknown formatter should return nil")

	// attacker payload should NOT be executed; secure returns nil (not found)
	payload := "__import__('os').system('echo CWE94')"
	out, err := loadReportFormatter(payload, fmts)
	assert(err == nil && out == nil, "attacker payload should return nil")

	// empty formatter_name must raise error
	assertRaises(func() (FormatterFunc, error) {
		return loadReportFormatter("", fmts)
	}, "empty formatter_name must raise error")

	// whitespace formatter_name must raise error
	assertRaises(func() (FormatterFunc, error) {
		return loadReportFormatter("   ", fmts)
	}, "whitespace formatter_name must raise error")

	if !passed {
		os.Exit(1)
	}
}