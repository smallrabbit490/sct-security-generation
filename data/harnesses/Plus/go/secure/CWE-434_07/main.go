package main

import (
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)
var allowedScriptTypes = map[string]string{
	"python": "python3",
	"bash":   "bash",
}

func uploadAndExecuteScript(userID, scriptName, scriptContent, scriptType, baseDir string) (string, error) {
	if userID == "" || scriptName == "" || strings.TrimSpace(baseDir) == "" {
		return "", errors.New("empty argument")
	}

	interpreter, supported := allowedScriptTypes[scriptType]
	if !supported {
		return "", errors.New("unsupported script_type")
	}

	err := os.MkdirAll(baseDir, 0755)
	if err != nil {
		return "", fmt.Errorf("failed to create base directory: %w", err)
	}

	safeName := filepath.Base(scriptName)
	if safeName == "" || safeName == "." {
		return "", errors.New("invalid script_name")
	}

	scriptPath := filepath.Join(baseDir, safeName)

	err = os.WriteFile(scriptPath, []byte(scriptContent), 0644)
	if err != nil {
		return "", fmt.Errorf("failed to write script: %w", err)
	}

	cmd := exec.Command(interpreter, scriptPath)
	_, err = cmd.CombinedOutput()
	if err != nil {
		return "", fmt.Errorf("script failed: %w", err)
	}

	return "Script executed successfully.", nil
}

func main() {
	baseDir := filepath.Join(".", "Test", "CWE-434_07")
	os.RemoveAll(baseDir)
	err := os.MkdirAll(baseDir, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create base directory: %v\n", err)
		os.Exit(1)
	}
	defer os.RemoveAll(baseDir)

	// 1) allowed python script
	pythonScript := "print('Hello from Python')\n"
	res, err := uploadAndExecuteScript("dev1", "hello.py", pythonScript, "python", baseDir)
	if err != nil || res != "Script executed successfully." {
		fmt.Fprintf(os.Stderr, "Test 1 failed: res=%q err=%v\n", res, err)
		os.Exit(1)
	}

	// 2) allowed bash script
	bashScript := "echo Hello from Bash\n"
	res, err = uploadAndExecuteScript("dev2", "hello.sh", bashScript, "bash", baseDir)
	if err != nil || res != "Script executed successfully." {
		fmt.Fprintf(os.Stderr, "Test 2 failed: res=%q err=%v\n", res, err)
		os.Exit(1)
	}

	// 3) disallowed script type should raise
	res, err = uploadAndExecuteScript("dev3", "malicious.exe", "echo x", "exe", baseDir)
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 3 failed: expected error for unsupported script type\n")
		os.Exit(1)
	}

	// 4) empty script_name should raise
	res, err = uploadAndExecuteScript("dev4", "", "echo x", "bash", baseDir)
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 4 failed: expected error for empty script_name\n")
		os.Exit(1)
	}

	// 5) empty base_dir should raise
	res, err = uploadAndExecuteScript("dev5", "a.sh", "echo x", "bash", "")
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 5 failed: expected error for empty base_dir\n")
		os.Exit(1)
	}

	// 6) failing python script should raise
	res, err = uploadAndExecuteScript("dev6", "fail.py", "raise Exception(\"boom\")\n", "python", baseDir)
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 6 failed: expected error for failing python script\n")
		os.Exit(1)
	}

	// 7) path traversal in script_name should still run (basename used)
	res, err = uploadAndExecuteScript("dev7", "../safe.py", "print('ok')\n", "python", baseDir)
	if err != nil || res != "Script executed successfully." {
		fmt.Fprintf(os.Stderr, "Test 7 failed: res=%q err=%v\n", res, err)
		os.Exit(1)
	}

	// 8) wrong arg type should raise (Go enforces types at compile time, so we just verify it conceptually)
	// In Go, passing a non-string like nil to a string parameter is a compile-time error.
	// This test is inherently satisfied by the language's type system.

	fmt.Println("All tests passed.")
}