package main

import (
	"fmt"
	"html"
	"net/url"
	"regexp"
	"strings"
)
var forbiddenCharsRegex = regexp.MustCompile(`[\s<>"']`)

func buildRedirectPage(targetUrl string) (string, error) {
	u := strings.TrimSpace(targetUrl)
	if u == "" {
		return "", fmt.Errorf("target_url must be non-empty")
	}

	if forbiddenCharsRegex.MatchString(u) {
		return "", fmt.Errorf("target_url contains forbidden characters")
	}

	parsed, err := url.Parse(u)
	if err != nil {
		return "", fmt.Errorf("invalid URL: %w", err)
	}

	if parsed.Scheme != "http" && parsed.Scheme != "https" {
		return "", fmt.Errorf("unsupported URL scheme")
	}

	if parsed.Host == "" {
		return "", fmt.Errorf("missing host")
	}

	safeU := html.EscapeString(u)

	return "<html><head><meta http-equiv=\"refresh\" content=\"0;url=" + safeU +
		"\"></head><body>Go to <a href=\"" + safeU + "\">" + safeU +
		"</a></body></html>", nil
}

func main() {
	passed := true

	assertRaises := func(fn func() (string, error)) {
		_, err := fn()
		if err == nil {
			fmt.Println("FAIL: Expected an error but none was raised")
			passed = false
		}
	}

	assertNoError := func(fn func() (string, error)) string {
		res, err := fn()
		if err != nil {
			fmt.Printf("FAIL: Unexpected error: %v\n", err)
			passed = false
		}
		return res
	}

	assertContains := func(s, substr string) {
		if !strings.Contains(s, substr) {
			fmt.Printf("FAIL: Expected substring %q not found in %q\n", substr, s)
			passed = false
		}
	}

	// Test valid URL with query parameters
	ok := "https://example.com/path?q=1&x=y"
	out := assertNoError(func() (string, error) { return buildRedirectPage(ok) })
	assertContains(out, "href=\"https://example.com/path?q=1&amp;x=y\"")
	assertContains(out, "content=\"0;url=https://example.com/path?q=1&amp;x=y\"")
	assertContains(out, "Go to")

	// Test another valid URL
	ok2 := "http://a.b/c"
	out2 := assertNoError(func() (string, error) { return buildRedirectPage(ok2) })
	assertContains(out2, "href=\"http://a.b/c\"")

	// Forbid javascript scheme
	assertRaises(func() (string, error) { return buildRedirectPage("javascript:alert(1)") })

	// Forbid relative path
	assertRaises(func() (string, error) { return buildRedirectPage("/relative/path") })

	// Forbid missing host
	assertRaises(func() (string, error) { return buildRedirectPage("https://") })

	// Forbid html-breaking characters / whitespace
	assertRaises(func() (string, error) { return buildRedirectPage("https://example.com/\" onmouseover=\"alert(1)") })
	assertRaises(func() (string, error) { return buildRedirectPage("https://example.com/a b") })
	assertRaises(func() (string, error) { return buildRedirectPage("<script>alert(1)</script>") })

	// Forbid empty / whitespace-only
	assertRaises(func() (string, error) { return buildRedirectPage("   ") })

	if !passed {
		panic("Validation failed")
	}
}