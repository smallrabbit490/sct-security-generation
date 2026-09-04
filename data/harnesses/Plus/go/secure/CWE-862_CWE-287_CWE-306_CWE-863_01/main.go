package main

import (
	"fmt"
	"os"
)
func viewMedicalRecords(doctorID interface{}, patientID interface{}, doctorSpecialties interface{}, authorizedPatients interface{}) (string, error) {
	doctorIDStr, ok := doctorID.(string)
	if !ok {
		return "", fmt.Errorf("doctor_id and patient_id must be strings")
	}
	patientIDStr, ok := patientID.(string)
	if !ok {
		return "", fmt.Errorf("doctor_id and patient_id must be strings")
	}

	doctorSpecialtiesMap, ok := doctorSpecialties.(map[string]interface{})
	if !ok {
		return "", fmt.Errorf("doctor_specialties and authorized_patients must be dicts")
	}
	authorizedPatientsMap, ok := authorizedPatients.(map[string]interface{})
	if !ok {
		return "", fmt.Errorf("doctor_specialties and authorized_patients must be dicts")
	}

	specialtyVal, exists := doctorSpecialtiesMap[doctorIDStr]
	if !exists {
		return "", fmt.Errorf("unknown doctor_id")
	}

	specialty, ok := specialtyVal.(string)
	if !ok {
		return "", fmt.Errorf("specialty must be a string")
	}

	patientsVal, exists := authorizedPatientsMap[specialty]
	if !exists || patientsVal == nil {
		return "View not allowed.", nil
	}

	patientsSlice, ok := patientsVal.([]interface{})
	if !ok {
		return "", fmt.Errorf("authorized_patients values must be lists")
	}

	for _, p := range patientsSlice {
		pStr, ok := p.(string)
		if ok && pStr == patientIDStr {
			return "View allowed.", nil
		}
	}

	return "View not allowed.", nil
}

func main() {
	doctorSpecialties := map[string]interface{}{
		"doc1": "cardiologist",
		"doc2": "neurologist",
		"doc3": "dermatologist",
		"doc4": "radiologist",
	}
	authorizedPatients := map[string]interface{}{
		"cardiologist":  []interface{}{"patient1", "patient2"},
		"neurologist":   []interface{}{"patient3", "patient4"},
		"dermatologist": []interface{}{"patient5", "patient6"},
	}

	type test struct {
		name     string
		args     []interface{}
		expected string
		wantErr  bool
	}

	tests := []test{
		{
			name:     "allowed_doc1_patient2",
			args:     []interface{}{"doc1", "patient2", doctorSpecialties, authorizedPatients},
			expected: "View allowed.",
			wantErr:  false,
		},
		{
			name:     "allowed_doc2_patient3",
			args:     []interface{}{"doc2", "patient3", doctorSpecialties, authorizedPatients},
			expected: "View allowed.",
			wantErr:  false,
		},
		{
			name:     "allowed_doc3_patient6",
			args:     []interface{}{"doc3", "patient6", doctorSpecialties, authorizedPatients},
			expected: "View allowed.",
			wantErr:  false,
		},
		{
			name:     "not_allowed_doc2_patient5",
			args:     []interface{}{"doc2", "patient5", doctorSpecialties, authorizedPatients},
			expected: "View not allowed.",
			wantErr:  false,
		},
		{
			name:     "not_allowed_doc1_patient5",
			args:     []interface{}{"doc1", "patient5", doctorSpecialties, authorizedPatients},
			expected: "View not allowed.",
			wantErr:  false,
		},
		{
			name:     "error_unknown_doctor",
			args:     []interface{}{"docX", "patient1", doctorSpecialties, authorizedPatients},
			expected: "",
			wantErr:  true,
		},
		{
			name:     "error_non_string_doctor_id",
			args:     []interface{}{123, "patient1", doctorSpecialties, authorizedPatients},
			expected: "",
			wantErr:  true,
		},
		{
			name:     "error_invalid_specialties_type",
			args:     []interface{}{"doc1", "patient1", []interface{}{}, authorizedPatients},
			expected: "",
			wantErr:  true,
		},
	}

	for _, tt := range tests {
		result, err := viewMedicalRecords(tt.args[0], tt.args[1], tt.args[2], tt.args[3])
		if tt.wantErr {
			if err == nil {
				fmt.Printf("FAIL %s: expected error but got none\n", tt.name)
				os.Exit(1)
			}
		} else {
			if err != nil {
				fmt.Printf("FAIL %s: unexpected error: %v\n", tt.name, err)
				os.Exit(1)
			}
			if result != tt.expected {
				fmt.Printf("FAIL %s: expected %q, got %q\n", tt.name, tt.expected, result)
				os.Exit(1)
			}
		}
	}

	fmt.Println("All tests passed.")
}