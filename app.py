from flask import Flask, render_template, request, redirect, url_for, make_response, session
import numpy as np
import pickle
import sqlite3
import csv
import io

app = Flask(__name__)
app.secret_key = 'super_secret_mca_project_key' 

# --- 1. DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('student_data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS history 
                 (id INTEGER PRIMARY KEY, name TEXT, roll_no TEXT, dept TEXT,
                  current_sem INTEGER, backlogs INTEGER, cgpa REAL, sgpa_history TEXT,
                  attendance REAL, assignments REAL, st1 REAL, st2 REAL, ct1 REAL, ct2 REAL,
                  grade REAL, risk_score REAL, status TEXT, advice TEXT, qt1 REAL, qt2 REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS admins 
                 (id INTEGER PRIMARY KEY, name TEXT, faculty_id TEXT UNIQUE, dept TEXT, password TEXT)''')
    conn.commit()
    conn.close()
init_db()

try:
    with open('model_grade.pkl', 'rb') as f: model_grade = pickle.load(f)
    with open('model_risk.pkl', 'rb') as f: model_risk = pickle.load(f)
except:
    pass

# --- 2. ROLE-TAILORED AI DIAGNOSIS ---
def generate_dynamic_diagnosis(att_pct, assign_pct, st_avg, ct_avg, backlogs, risk, is_admin):
    diagnosis = []
    
    if is_admin:
        if risk > 60:
            diagnosis.append("🚨 <b>URGENT - High Dropout Risk:</b> This student is critically at risk of failing. Please schedule a mandatory 1-on-1 counseling session immediately.")
        elif risk > 30:
            diagnosis.append("⚠️ <b>Monitor Closely:</b> Student is showing warning signs of falling behind. Recommend assigning a peer mentor.")
        else:
            diagnosis.append("🌟 <b>On Track:</b> Student is performing well. Encourage them to maintain consistency.")

        if backlogs > 0:
            diagnosis.append(f"📌 <b>Intervention Required:</b> Student has {backlogs} active backlogs. Discuss a specific clearance strategy and roadmap with them.")
        if att_pct < 65:
            diagnosis.append(f"🚫 <b>Attendance Alert:</b> Attendance is critically low ({round(att_pct)}%). Warn the student regarding university debarment policies.")
        if st_avg < 50 or ct_avg < 50:
            diagnosis.append("📉 <b>Focus Area:</b> Student is struggling in internal tests. Recommend remedial classes before the final exams.")
            
    else:
        if risk > 60:
            diagnosis.append("🚨 <b>CRITICAL ACADEMIC RISK:</b> You are at a high risk of dropping out or failing.")
            diagnosis.append("📞 <b>ACTION REQUIRED:</b> Please contact your Faculty Advisor or HOD immediately for guidance and support.")
        elif risk > 30:
            diagnosis.append("⚠️ <b>Warning:</b> Your academic trajectory is slipping. It's time to focus and seek help if needed.")
        else:
            diagnosis.append("🌟 <b>Star Performer:</b> Your profile is balanced and consistent. Keep up the great work!")

        if backlogs > 0:
            diagnosis.append(f"⛔ <b>Backlog Focus:</b> You have {backlogs} active backlogs. Stop new extracurricular projects and make clearing these your #1 priority.")
        if att_pct < 65:
            diagnosis.append(f"🚫 <b>Debarment Risk:</b> At {round(att_pct)}% attendance, you may not be allowed to write your exams. Attend all remaining classes.")
            
    return diagnosis

# --- 3. DASHBOARD DATA PREP ---
def prep_dashboard_data(row, is_admin):
    name, roll_no = row[1], row[2]
    backlogs, cgpa = row[5], row[6]
    sgpa_str = row[7]
    sgpa_list = [float(x) for x in sgpa_str.split(',')] if sgpa_str else []
    att_pct, assign_pct = row[8], row[9]
    st1_pct, st2_pct = row[10], row[11]
    ct1_pct, ct2_pct = row[12], row[13]
    grade, risk = row[14], row[15]
    status = row[16]
    qt1_pct, qt2_pct = row[18], row[19] 
    
    st_avg = (st1_pct + st2_pct) / 2
    ct_avg = (ct1_pct + ct2_pct) / 2

    breakdown = {
        'att_contrib': round((0.05 * att_pct) / 10, 2),
        'assign_contrib': round((0.15 * assign_pct) / 10, 2),
        'st_contrib': round((0.20 * st_avg) / 10, 2),
        'ct_contrib': round((0.20 * ct_avg) / 10, 2),
        'cgpa_contrib': round((4.0 * cgpa) / 10, 2),
        'backlog_penalty': round((5 * backlogs) / 10, 2)
    }
    
    color = "bg-danger" if risk > 60 else "bg-warning text-dark" if risk > 30 else "bg-success"
    dynamic_advice = generate_dynamic_diagnosis(att_pct, assign_pct, st_avg, ct_avg, backlogs, risk, is_admin)

    return {
        'is_admin': is_admin, 'student_id': row[0],
        'name': f"{name} ({roll_no})" if is_admin else name,
        'grade': grade, 'status': status, 'color': color, 'risk_score': risk,
        'advice_list': dynamic_advice,
        'sgpa_history': sgpa_list, 'backlogs': backlogs, 'cgpa': cgpa,
        'att': att_pct, 'assign': assign_pct, 'st1': st1_pct, 'st2': st2_pct,
        'ct1': ct1_pct, 'ct2': ct2_pct, 'qt1': qt1_pct, 'qt2': qt2_pct, 'bd': breakdown
    }

# ==================== ROUTES ====================

@app.route('/')
def role_selection(): return render_template('role.html')

@app.route('/logout')
def logout():
    session.clear() 
    return redirect(url_for('role_selection'))

@app.route('/student_login')
def student_login(): return render_template('student_login.html')

@app.route('/student_auth', methods=['POST'])
def student_auth():
    roll_no, dept = request.form['roll_no'], request.form['dept']
    conn = sqlite3.connect('student_data.db')
    c = conn.cursor()
    c.execute("SELECT * FROM history WHERE roll_no=? AND dept=? ORDER BY id DESC LIMIT 1", (roll_no, dept))
    row = c.fetchone()
    conn.close()
    if not row: return render_template('error.html') 
    return render_template('dashboard.html', **prep_dashboard_data(row, is_admin=False))

@app.route('/admin_login')
def admin_login():
    return render_template('admin_login.html', error=request.args.get('error'), success=request.args.get('success'))

# >>> UPDATED SECURE FACULTY REGISTRATION ROUTE <<<
@app.route('/admin_register', methods=['GET', 'POST'])
def admin_register():
    if request.method == 'POST':
        # 1. Check the secret authorization code first
        auth_code = request.form.get('auth_code')
        if auth_code != "ABIT-FACULTY-2026":
            return render_template('admin_register.html', error="🚨 Invalid College Authorization Code! Registration Denied.")

        # 2. If the code is correct, proceed with saving the new admin
        conn = sqlite3.connect('student_data.db')
        c = conn.cursor()
        try:
            c.execute("INSERT INTO admins (name, faculty_id, dept, password) VALUES (?, ?, ?, ?)", 
                      (request.form['name'], request.form['faculty_id'], request.form['dept'], request.form['password']))
            conn.commit()
            conn.close()
            return redirect(url_for('admin_login', success="Registration successful! Please log in."))
        except sqlite3.IntegrityError:
            conn.close()
            return render_template('admin_register.html', error="This Faculty ID is already registered!")
            
    return render_template('admin_register.html')

@app.route('/admin_auth', methods=['POST'])
def admin_auth():
    conn = sqlite3.connect('student_data.db')
    c = conn.cursor()
    c.execute("SELECT * FROM admins WHERE faculty_id=? AND password=?", (request.form['faculty_id'], request.form['password']))
    admin = c.fetchone()
    conn.close()
    
    if admin: 
        session['admin_name'] = admin[1] 
        session['admin_dept'] = admin[3] 
        return redirect(url_for('admin_panel'))
    else: 
        return redirect(url_for('admin_login', error="Invalid Faculty ID or Password!"))

@app.route('/admin')
def admin_panel():
    if 'admin_name' not in session:
        return redirect(url_for('admin_login', error="Please log in first."))

    current_teacher_dept = session['admin_dept']

    conn = sqlite3.connect('student_data.db')
    c = conn.cursor()
    c.execute("SELECT * FROM history WHERE dept=?", (current_teacher_dept,))
    data = c.fetchall()
    conn.close()

    grouped_students = {}
    for student in data:
        roll_no = str(student[2]) 
        year_digits = roll_no[:2] 
        batch_year = f"20{year_digits}" if year_digits.isdigit() and len(year_digits) >= 2 else "Unknown Batch"
        if batch_year not in grouped_students: grouped_students[batch_year] = []
        grouped_students[batch_year].append(student)

    for batch in grouped_students:
        grouped_students[batch].sort(key=lambda x: str(x[2]))
    sorted_batches = dict(sorted(grouped_students.items()))

    return render_template('admin.html', grouped_students=sorted_batches, total_count=len(data), 
                           admin_name=session['admin_name'], admin_dept=session['admin_dept'])

@app.route('/add_student')
def add_student(): return render_template('student_details.html')

@app.route('/academic_input', methods=['POST'])
def academic_input():
    return render_template('index.html', name=request.form['name'], roll_no=request.form['roll_no'], dept=request.form['dept'])

# >>> CORE LOGIC HANDLER <<<
def process_academic_data(form_data, student_id=None):
    current_sem = int(form_data['current_sem'])
    backlogs = int(form_data['backlogs'])
    
    sgpa_list = [float(form_data.get(f'sgpa_{i}', 0)) for i in range(1, current_sem)]
    cgpa = sum(sgpa_list) / len(sgpa_list) if sgpa_list else 0
    sgpa_str = ",".join(map(str, sgpa_list)) 

    att_pct = (float(form_data['attended_classes']) / max(float(form_data['total_classes']), 1)) * 100
    assign_pct = (float(form_data['submitted_assign']) / max(float(form_data['total_assign']), 1)) * 100
    st1_pct = (float(form_data['st1_score']) / max(float(form_data['st1_total']), 1)) * 100
    st2_pct = (float(form_data['st2_score']) / max(float(form_data['st2_total']), 1)) * 100
    ct1_pct = (float(form_data['ct1_score']) / max(float(form_data['ct1_total']), 1)) * 100
    ct2_pct = (float(form_data['ct2_score']) / max(float(form_data['ct2_total']), 1)) * 100
    qt1_pct = (float(form_data['qt1_score']) / max(float(form_data['qt1_total']), 1)) * 100
    qt2_pct = (float(form_data['qt2_score']) / max(float(form_data['qt2_total']), 1)) * 100

    st_avg = (st1_pct + st2_pct) / 2
    ct_avg = (ct1_pct + ct2_pct) / 2
    
    features = np.array([[att_pct, assign_pct, st_avg, ct_avg, cgpa, backlogs]])
    raw_grade = model_grade.predict(features)[0]
    predicted_grade = round(raw_grade / 10, 2) 
    
    features_for_risk = np.array([[att_pct, assign_pct, st_avg, ct_avg, cgpa, 0]])
    base_risk = model_risk.predict_proba(features_for_risk)[0][1]
    risk_probability = base_risk
    
    risk_probability += (backlogs * 0.15) 
    
    all_metrics = [att_pct, assign_pct, st1_pct, st2_pct, ct1_pct, ct2_pct, qt1_pct, qt2_pct]
    lowest_metric = min(all_metrics)

    penalty = backlogs * 0.15
    for m in all_metrics:
        if m < 50:
            penalty += (50 - m) * 0.01   
        elif m < 75:
            penalty += (75 - m) * 0.002  

    risk_probability += penalty

    if lowest_metric < 50:
        if risk_probability <= 0.60:
            cgpa_factor = max(0, 10 - cgpa) / 10 
            risk_probability = 0.61 + (cgpa_factor * 0.30) + ((50 - lowest_metric) * 0.005)

    elif lowest_metric < 75:
        if risk_probability <= 0.30:
            cgpa_factor = max(0, 10 - cgpa) / 10
            risk_probability = 0.31 + (cgpa_factor * 0.20) + ((75 - lowest_metric) * 0.004)
            
    risk_probability = min(risk_probability, 0.99)
    status = "At Risk ⚠️" if risk_probability > 0.6 else "Warning ⚠️" if risk_probability > 0.3 else "Safe ✅"

    conn = sqlite3.connect('student_data.db')
    c = conn.cursor()
    
    if student_id:
        c.execute("""UPDATE history SET current_sem=?, backlogs=?, cgpa=?, sgpa_history=?, 
                     attendance=?, assignments=?, st1=?, st2=?, ct1=?, ct2=?, qt1=?, qt2=?, 
                     grade=?, risk_score=?, status=? WHERE id=?""",
                  (current_sem, backlogs, round(cgpa, 2), sgpa_str, round(att_pct, 1), round(assign_pct, 1), 
                   round(st1_pct, 1), round(st2_pct, 1), round(ct1_pct, 1), round(ct2_pct, 1), round(qt1_pct, 1), round(qt2_pct, 1),
                   predicted_grade, round(risk_probability*100, 1), status, student_id))
        target_id = student_id
    else:
        c.execute("""INSERT INTO history (name, roll_no, dept, current_sem, backlogs, cgpa, sgpa_history, 
                     attendance, assignments, st1, st2, ct1, ct2, grade, risk_score, status, advice, qt1, qt2) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                  (form_data['name'], form_data['roll_no'], form_data['dept'], current_sem, backlogs, round(cgpa, 2), sgpa_str, 
                   round(att_pct, 1), round(assign_pct, 1), round(st1_pct, 1), round(st2_pct, 1), round(ct1_pct, 1), round(ct2_pct, 1), 
                   predicted_grade, round(risk_probability*100, 1), status, "", round(qt1_pct, 1), round(qt2_pct, 1)))
        target_id = c.lastrowid
        
    conn.commit()
    conn.close()
    return target_id

@app.route('/predict', methods=['POST'])
def predict():
    try:
        last_id = process_academic_data(request.form)
        return redirect(url_for('view_student_dashboard', student_id=last_id))
    except Exception as e:
        return f"<h3>Error:</h3><p>{e}</p>"

@app.route('/student/<int:student_id>')
def view_student_dashboard(student_id):
    conn = sqlite3.connect('student_data.db')
    c = conn.cursor()
    c.execute("SELECT * FROM history WHERE id=?", (student_id,))
    row = c.fetchone()
    conn.close()
    if not row: return "Student not found.", 404
    return render_template('dashboard.html', **prep_dashboard_data(row, is_admin=True))

@app.route('/delete/<int:student_id>', methods=['POST'])
def delete_student(student_id):
    conn = sqlite3.connect('student_data.db')
    c = conn.cursor()
    c.execute("DELETE FROM history WHERE id=?", (student_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/edit/<int:student_id>')
def edit_student(student_id):
    conn = sqlite3.connect('student_data.db')
    c = conn.cursor()
    c.execute("SELECT * FROM history WHERE id=?", (student_id,))
    row = c.fetchone()
    conn.close()
    if not row: return "Student not found.", 404
    sgpa_str = row[7]
    sgpa_list = [float(x) for x in sgpa_str.split(',')] if sgpa_str else []
    return render_template('edit_student.html', student=row, sgpa_list=sgpa_list)

@app.route('/update/<int:student_id>', methods=['POST'])
def update_student(student_id):
    try:
        process_academic_data(request.form, student_id=student_id)
        return redirect(url_for('view_student_dashboard', student_id=student_id))
    except Exception as e:
        return f"<h3>Error Updating:</h3><p>{e}</p>"

@app.route('/export_excel/<batch_year>')
def export_excel(batch_year):
    if 'admin_dept' not in session:
        return redirect(url_for('admin_login'))

    current_teacher_dept = session['admin_dept']

    conn = sqlite3.connect('student_data.db')
    c = conn.cursor()
    c.execute("SELECT * FROM history WHERE dept=? ORDER BY roll_no ASC", (current_teacher_dept,))
    data = c.fetchall()
    conn.close()

    filtered_data = []
    for student in data:
        roll_no = str(student[2])
        year_digits = roll_no[:2]
        student_batch = f"20{year_digits}" if year_digits.isdigit() and len(year_digits) >= 2 else "Unknown Batch"
        
        if student_batch == batch_year and "Safe" not in student[16]:
            safe_roll_no = f'="{roll_no}"' 
            
            clean_row = [
                student[1], safe_roll_no, student[3], student[4], 
                student[8], student[9], student[10], student[11], 
                student[12], student[13], student[18], student[19],
                student[15], student[16] 
            ]
            filtered_data.append(clean_row)

    si = io.StringIO()
    si.write('\ufeff') 
    cw = csv.writer(si)
    
    cw.writerow(['Student Name', 'Regd. No', 'Department', 'Current Sem', 
                 'Attendance (%)', 'Assignments (%)', 'ST1 (%)', 'ST2 (%)', 
                 'CT1 (%)', 'CT2 (%)', 'QT1 (%)', 'QT2 (%)', 'Risk Score (%)', 'Risk Status'])
    
    cw.writerows(filtered_data)

    output = make_response(si.getvalue())
    safe_filename = batch_year.replace(" ", "_")
    output.headers["Content-Disposition"] = f"attachment; filename={current_teacher_dept}_{safe_filename}_At_Risk_Report.csv"
    output.headers["Content-type"] = "text/csv; charset=utf-8" 
    return output

if __name__ == '__main__':
    app.run(debug=True)