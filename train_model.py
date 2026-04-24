import pandas as pd
import numpy as np
import pickle
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

# 1. Generate Synthetic Data (Simulating 1000 past students)
np.random.seed(42)
n_samples = 1000

data = {
    'attendance_pct': np.random.uniform(50, 100, n_samples),
    'assignment_pct': np.random.uniform(50, 100, n_samples),
    'surprise_test_pct': np.random.uniform(30, 100, n_samples),
    'class_test_pct': np.random.uniform(30, 100, n_samples),
    'previous_cgpa': np.random.uniform(4.0, 10.0, n_samples), # Historical Data
    'backlogs': np.random.choice([0, 0, 0, 1, 2, 3], n_samples) # 0 is most common
}
df = pd.DataFrame(data)

# Logic: Final Grade Calculation
# Past CGPA and Backlogs now heavily influence the outcome
df['final_grade'] = (
    0.05 * df['attendance_pct'] + 
    0.15 * df['assignment_pct'] + 
    0.20 * df['surprise_test_pct'] + 
    0.20 * df['class_test_pct'] + 
    4.0 * df['previous_cgpa'] + 
    np.random.normal(0, 5, n_samples)
).clip(0, 100)

# Penalty: Backlogs drag the grade down
df['final_grade'] -= (df['backlogs'] * 5) 

# Logic: Risk Classifier (High Risk if Grade < 50 OR Backlogs > 2)
df['dropout_risk'] = np.where((df['final_grade'] < 50) | (df['backlogs'] >= 2), 1, 0)

# 2. Train Models
# Features must match app.py input order exactly!
X = df[['attendance_pct', 'assignment_pct', 'surprise_test_pct', 'class_test_pct', 'previous_cgpa', 'backlogs']]
y_grade = df['final_grade']
y_risk = df['dropout_risk']

print("Training Grade Predictor...")
model_grade = RandomForestRegressor(n_estimators=100)
model_grade.fit(X, y_grade)

print("Training Risk Classifier...")
model_risk = RandomForestClassifier(n_estimators=100)
model_risk.fit(X, y_risk)

# 3. Save Models
with open('model_grade.pkl', 'wb') as f:
    pickle.dump(model_grade, f)

with open('model_risk.pkl', 'wb') as f:
    pickle.dump(model_risk, f)

print("✅ Success! Final Product Models (with SGPA/Backlogs) Saved.")