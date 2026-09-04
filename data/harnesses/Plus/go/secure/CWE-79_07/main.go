package main

import (
	"fmt"
	"html"
	"strings"
)
// ProfileData represents the input structure for the render function.
type ProfileData struct {
	ProfileTemplate string
	PageData        map[string]interface{}
}

// renderProfilePage replaces placeholders in the template with safely escaped values from pageData.
func renderProfilePage(profileData ProfileData) (string, error) {
	if profileData.ProfileTemplate == "" && profileData.PageData == nil {
		return "", fmt.Errorf("missing required keys")
	}

	template := profileData.ProfileTemplate
	pageData := profileData.PageData

	if template == "" {
		return "", fmt.Errorf("invalid profile_template")
	}
	if pageData == nil {
		return "", fmt.Errorf("invalid page_data")
	}

	safeData := make(map[string]string)
	for k, v := range pageData {
		safeData[k] = html.EscapeString(fmt.Sprintf("%v", v))
	}

	result := template

	for k, v := range safeData {
		placeholder := "{" + k + "}"
		result = strings.ReplaceAll(result, placeholder, v)
	}

	// Check for any remaining placeholders that were not provided in pageData
	remainingPlaceholders := extractPlaceholders(result)
	if len(remainingPlaceholders) > 0 {
		return "", fmt.Errorf("missing key(s) for placeholder(s): %s", strings.Join(remainingPlaceholders, ", "))
	}

	return result, nil
}

// extractPlaceholders finds all {key} patterns in the template string.
func extractPlaceholders(s string) []string {
	var keys []string
	inBrace := false
	var currentKey strings.Builder

	for _, r := range s {
		if r == '{' {
			inBrace = true
			currentKey.Reset()
		} else if r == '}' && inBrace {
			inBrace = false
			key := currentKey.String()
			if key != "" {
				keys = append(keys, key)
			}
		} else if inBrace {
			currentKey.WriteRune(r)
		}
	}
	return keys
}

func assertRaises(fn func() error, expectedErr string) {
	err := fn()
	if err == nil {
		panic(fmt.Sprintf("expected error containing %q, got nil", expectedErr))
	}
	if !strings.Contains(err.Error(), expectedErr) {
		panic(fmt.Sprintf("expected error containing %q, got %q", expectedErr, err.Error()))
	}
}

func main() {
	// Test 1: Normal replacement
	profileData1 := ProfileData{
		ProfileTemplate: "<div><h1>{title}</h1><p>{description}</p></div>",
		PageData: map[string]interface{}{
			"title":       "Safe Profile",
			"description": "Welcome to my profile.",
		},
	}
	result1, err1 := renderProfilePage(profileData1)
	if err1 != nil {
		panic(err1)
	}
	expected1 := "<div><h1>Safe Profile</h1><p>Welcome to my profile.</p></div>"
	if result1 != expected1 {
		panic(fmt.Sprintf("expected %q, got %q", expected1, result1))
	}

	// Test 2: XSS escaping
	profileData2 := ProfileData{
		ProfileTemplate: "<div>{bio}</div>",
		PageData: map[string]interface{}{
			"bio": "<script>alert(\"X\")</script>",
		},
	}
	result2, err2 := renderProfilePage(profileData2)
	if err2 != nil {
		panic(err2)
	}
	expected2 := "<div>&lt;script&gt;alert(&#34;X&#34;)&lt;/script&gt;</div>"
	if result2 != expected2 {
		panic(fmt.Sprintf("expected %q, got %q", expected2, result2))
	}

	// Test 3: Mixed HTML characters
	profileData3 := ProfileData{
		ProfileTemplate: "<span>{x}</span>",
		PageData: map[string]interface{}{
			"x": "A & B < C",
		},
	}
	result3, err3 := renderProfilePage(profileData3)
	if err3 != nil {
		panic(err3)
	}
	expected3 := "<span>A &amp; B &lt; C</span>"
	if result3 != expected3 {
		panic(fmt.Sprintf("expected %q, got %q", expected3, result3))
	}

	// Test 4: Numeric value
	profileData4 := ProfileData{
		ProfileTemplate: "<p>{n}</p>",
		PageData: map[string]interface{}{
			"n": 123,
		},
	}
	result4, err4 := renderProfilePage(profileData4)
	if err4 != nil {
		panic(err4)
	}
	expected4 := "<p>123</p>"
	if result4 != expected4 {
		panic(fmt.Sprintf("expected %q, got %q", expected4, result4))
	}

	// Test 5: Missing keys
	assertRaises(func() error {
		_, err := renderProfilePage(ProfileData{
			ProfileTemplate: "<p>{missing}</p>",
			PageData:        map[string]interface{}{},
		})
		return err
	}, "missing key(s)")

	// Test 6: Missing required keys
	assertRaises(func() error {
		_, err := renderProfilePage(ProfileData{})
		return err
	}, "missing required keys")

	// Test 7: Invalid profile_template
	assertRaises(func() error {
		_, err := renderProfilePage(ProfileData{
			ProfileTemplate: "",
			PageData:        map[string]interface{}{},
		})
		return err
	}, "invalid profile_template")

	// Test 8: Invalid page_data
	assertRaises(func() error {
		_, err := renderProfilePage(ProfileData{
			ProfileTemplate: "template",
			PageData:        nil,
		})
		return err
	}, "invalid page_data")

	fmt.Println("All tests passed!")
}