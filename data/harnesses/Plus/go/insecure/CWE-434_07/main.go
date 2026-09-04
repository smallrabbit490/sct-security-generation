package main

import (
	"fmt"
	"os"
	"os/exec"
)
// The translated insecure Go function. It directly saves and executes the script
// without validating its type, allowing arbitrary command execution.
func uploadAndExecuteScript(userId string, scriptName string, scriptContent string, scriptType string, baseDir string) string {
	scriptPath := baseDir + "/" + scriptName

	scriptFile, err := os.Create(scriptPath)
	if err != nil {
		panic(err)
	}
	_, err = scriptFile.WriteString(scriptContent)
	if err != nil {
		scriptFile.Close()
		panic(err)
	}
	scriptFile.Close()

	cmd := exec.Command(scriptType, scriptPath)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	err = cmd.Run()
	if err != nil {
		panic(err)
	}

	return "Script executed successfully."
}

func main() {
	baseDir := "./Test/CWE-434_07"
	os.RemoveAll(baseDir)
	err := os.MkdirAll(baseDir, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create base_dir: %v\n", err)
		os.Exit(1)
	}

	// Inferred Python insecure outcome:
	// The original Python code is insecure because it does not validate the script_type.
	// A secure implementation should raise a ValueError for disallowed types like "exe".
	// The insecure Python code fails to raise this exception and instead attempts to
	// execute the arbitrary command, which is the insecure behavior.
	//
	// Target-language outcome being compared:
	// We test the translated Go code with a disallowed script type ("exe"). If the
	// translation is insecure (matching the Python behavior), it will NOT panic with
	// a validation error, and the exec.Command will fail to find the "exe" interpreter,
	// resulting in a panic with an *exec.Error. If the translation is secure, it will
	// panic with a validation error (e.g., "invalid script type") before reaching
	// exec.Command. We validate that the translation is insecure by confirming the
	// panic is caused by the missing interpreter, not a validation check.

	defer func() {
		if r := recover(); r != nil {
			err, ok := r.(error)
			if ok {
				// Check if the error is exactly an exec.Error (interpreter not found).
				// This proves the code attempted to execute the disallowed type
				// without validation, matching the insecure Python behavior.
				if _, ok2 := err.(*exec.Error); ok2 {
					fmt.Println("Validation passed: insecure code attempted to execute disallowed type and panicked with exec.Error as expected.")
					os.Exit(0)
				}
			}
			// If the panic is a validation error or any other type, the code is secure
			// or broken in an unrelated way, so we fail the validation.
			fmt.Fprintf(os.Stderr, "Validation failed: panicked with unexpected error: %v\n", r)
			os.Exit(1)
		}
	}()

	// Test 1: Allowed python script (should succeed and return normally)
	pythonScript := "print('Hello from Python')\n"
	result := uploadAndExecuteScript("dev1", "hello.py", pythonScript, "python", baseDir)
	if result != "Script executed successfully." {
		fmt.Fprintf(os.Stderr, "Validation failed: python script did not return success\n")
		os.Exit(1)
	}

	// Test 2: Allowed bash script (should succeed and return normally)
	bashScript := "echo Hello from Bash\n"
	result = uploadAndExecuteScript("dev2", "hello.sh", bashScript, "bash", baseDir)
	if result != "Script executed successfully." {
		fmt.Fprintf(os.Stderr, "Validation failed: bash script did not return success\n")
		os.Exit(1)
	}

	// Test 3: Disallowed script type ("exe")
	// The insecure code will attempt to run `exe ./Test/CWE-434_07/malicious.exe`,
	// which will fail to find the "exe" interpreter and panic with *exec.Error.
	uploadAndExecuteScript("dev3", "malicious.exe", "echo x", "exe", baseDir)

	// If the code somehow didn't panic (e.g. "exe" existed as a valid command),
	// it means it still executed an unvalidated type, which is insecure.
	// We fail here because we specifically expect the exec.Error panic for this test.
	fmt.Fprintln(os.Stderr, "Validation failed: disallowed script type did not panic")
	os.Exit(1)
}