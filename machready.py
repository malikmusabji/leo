import streamlit as st
import sqlite3
import pandas as pd
from PyPDF2 import PdfReader
import io
import os
import requests
import bcrypt
import pytz
import uuid
import base64
from datetime import datetime, timedelta


def login_page():
    st.subheader("Login")
    user_id = st.text_input("User ID (Numerical Only)")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if not user_id or not password:
            st.warning("Please enter both User ID and Password.")
            return

        if not user_id.isdigit():
            st.error("User ID must be numerical.")
            return

        user_type = authenticate(user_id, password)
        if user_type:
            st.session_state["logged_in"] = True
            st.session_state["user_id"] = user_id
            st.session_state["user_role"] = user_type
            st.success(f"Login successful! Welcome, {user_type.capitalize()}.")
            st.session_state["username"] = user_id
            st.success(f"Welcome, {user_id}!")
            st.session_state.login_time = datetime.now(pytz.timezone(get_user_timezone()))
            st.session_state.login_status = True
            return True
        else:
            st.error("Invalid User ID or Password.")

def seed_users():
    """Seed the database with default teacher and student users for testing."""
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()

        # Check if users already exist in the database
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]

        if count > 0:
            print("Users already exist. Skipping seeding.")
            return  # Exit if users already exist

        # Add default teacher and student credentials
        users = [
            ("12345", bcrypt.hashpw("teacher_pass".encode('utf-8'), bcrypt.gensalt()), "teacher"),
            ("1234", bcrypt.hashpw("student_pass".encode('utf-8'), bcrypt.gensalt()), "student"),
        ]
        cursor.executemany("INSERT INTO users (user_id, password_hash, user_type) VALUES (?, ?, ?)", users)
        conn.commit()
        print("Default users seeded successfully!")
    except Exception as e:
        print(f"Error seeding users: {e}")
    finally:
        conn.close()

def save_teacher_attendance(present_students):
    """Save the attendance of the selected students to the database."""
    try:
        date_today = datetime.now().strftime("%Y-%m-%d")
        conn = sqlite3.connect("attendance.db")
        cursor = conn.cursor()
        
        # Create a table for attendance records if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attendance_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                student_name TEXT NOT NULL
            )
        """)

        # Insert attendance records for present students
        for student in present_students:
            cursor.execute("INSERT INTO attendance_records (date, student_name) VALUES (?, ?)", (date_today, student))
        
        conn.commit()
        st.success(f"Attendance recorded for {len(present_students)} students on {date_today}.")
    except Exception as e:
        st.error(f"An error occurred while recording attendance: {e}")
    finally:
        conn.close()

def materials_dashboard():
    st.title("Learning Materials")
    os.makedirs("uploaded_materials", exist_ok=True)
    if st.session_state["user_role"] == "teacher":
        # Teacher can upload files
        uploaded_file = st.file_uploader("Upload Materials", type=['pdf', 'docx', 'pptx'])
        if uploaded_file:
            save_material(uploaded_file)
    materials = fetch_uploaded_materials()
    if materials:
        st.subheader("Available Materials")
        for idx, (filename, upload_time) in enumerate(materials):
            file_path = os.path.join("uploaded_materials", filename)
            with open(file_path, "rb") as f:
                st.download_button(f"Download {filename}", f, file_name=filename, key=f"download-{idx}")
    else:
        st.info("No materials have been uploaded yet.")


def mark_attendance_dashboard():
    role = st.session_state["user_role"]
    username = st.session_state["user_id"]

    st.title(f"{role.capitalize()} Dashboard - Attendance")
    if role == "teacher":
        # Teacher selects students
        students = [f"Student {i+1}" for i in range(1234)]
        present_students = st.multiselect("Select students who are present", students)
        if st.button("Submit Attendance"):
            if present_students:
                save_teacher_attendance(present_students)  # Now defined
            else:
                st.warning("Please select at least one student.")


def get_user_role(username):
    """Determine if the user is a teacher or student based on the username."""
    if username.isdigit():  # Ensure username is numerical
        if len(username) == 5:
            return "teacher"
        elif len(username) < 5:
            return "student"
    return None

# Initialize database for "present_today"
def init_present_today_db():
    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS present_today (
            username TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

# Validate the code
def validate_code(input_code):
    try:
        conn = sqlite3.connect("codes.db")
        cursor = conn.cursor()

        # Check the code against the database
        cursor.execute("SELECT expiration_time FROM codes WHERE code = ?", (input_code,))
        result = cursor.fetchone()

        if result:
            expiration_time = datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S")
            if datetime.now() <= expiration_time:
                return True  # Code is valid

        return False  # Code is invalid or expired
    except sqlite3.Error as e:
        st.error(f"Error validating the code: {e}")
        return False  # Return False in case of database errors
    finally:
        conn.close()


# Function to get user's timezone based on IP address
def get_user_timezone():
    try:
        response = requests.get("https://ipinfo.io/json")
        if response.status_code == 200:
            data = response.json()
            return data.get("timezone", "UTC")
    except:
        pass
    return "UTC"

# Function to display flip clock based on the user's time zone
def display_flip_clock():
    user_timezone = get_user_timezone()
    now = datetime.now(pytz.timezone(user_timezone))

    flipclock_html = f"""
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/flipclock/0.7.8/flipclock.min.css">
    <div id="flip-clock" style="display: flex; justify-content: center;"></div>
    
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jquery/3.6.0/jquery.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/flipclock/0.7.8/flipclock.min.js"></script>
    <script type="text/javascript">
        document.addEventListener("DOMContentLoaded", function() {{
            var clock = new FlipClock(document.getElementById('flip-clock'), {{
                clockFace: 'TwentyFourHourClock',
                showSeconds: true
            }});
        }});
    </script>
    """
    
    st.components.v1.html(flipclock_html, height=150)

# Function to add JavaScript for detecting tab changes
def detect_tab_switch():
    js_code = """
    <script>
        document.addEventListener("visibilitychange", function() {
            if (document.hidden) {
                alert("You are moving away from this page! Please stay on this tab.");
            }
        });
    </script>
    """
    st.components.v1.html(js_code)

def display_session_timer():
    if "login_time" in st.session_state:
        # Calculate the elapsed time since login in seconds
        elapsed_time = (datetime.now(pytz.timezone(get_user_timezone())) - st.session_state.login_time).total_seconds()
        session_timer_html = f"""
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/flipclock/0.7.8/flipclock.min.css">
        <div id="session-timer" style="display: flex; justify-content: center;"></div>
        
        <script src="https://cdnjs.cloudflare.com/ajax/libs/jquery/3.6.0/jquery.min.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/flipclock/0.7.8/flipclock.min.js"></script>
        <script type="text/javascript">
            document.addEventListener("DOMContentLoaded", function() {{
                var timer = new FlipClock(document.getElementById('session-timer'), {{
                    clockFace: 'MinuteCounter',
                    autoStart: true
                }});
                // Set the timer to start from the elapsed time
                timer.setTime({int(elapsed_time)});
                timer.start();
            }});
        </script>
        """
        
        st.components.v1.html(session_timer_html, height=150)

# Initialize database for codes
def init_code_db():
    conn = sqlite3.connect("codes.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS codes (
            code TEXT PRIMARY KEY,
            expiration_time TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

# Generate a unique code
def generate_unique_code():
    init_code_db()
    conn = sqlite3.connect("codes.db")
    cursor = conn.cursor()

    # Generate a unique code and calculate expiration time
    unique_code = str(uuid.uuid4())[:8]
    expiration_time = datetime.now() + timedelta(minutes=6)

    # Store the code and expiration time in the database
    cursor.execute("INSERT INTO codes (code, expiration_time) VALUES (?, ?)", 
                   (unique_code, expiration_time.strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    return unique_code, expiration_time


# Authenticate user by checking credentials in the database
def authenticate(user_id, password):
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute("SELECT password_hash, user_type FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        conn.close()

        if user:
            hashed_password, user_type = user
            if bcrypt.checkpw(password.encode('utf-8'), hashed_password):
                return user_type
        return None
    except Exception as e:
        st.error(f"Error during authentication: {e}")
        return None

def save_material(uploaded_file):
    # Ensure directory exists
    os.makedirs("uploaded_materials", exist_ok=True)
    conn = sqlite3.connect("shared_materials.db")
    cursor = conn.cursor()
    upload_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        # Save file to directory
        file_path = os.path.join("uploaded_materials", uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        # Save metadata to the database
        cursor.execute("INSERT INTO materials (filename, upload_time) VALUES (?, ?)", 
                       (uploaded_file.name, upload_time))
        conn.commit()
        st.success(f"File '{uploaded_file.name}' uploaded successfully!")
    except Exception as e:
        st.error(f"Failed to upload file: {e}")
    finally:
        conn.close()

# Professor Dashboard (Core App Functionality)
def professor_dashboard():
    st.title("Professor Dashboard")

    # Attendance section
    st.subheader("Take Attendance")

    # Simulated list of students
    students = [f"Student {i+1}" for i in range(1234)]
    present_students = st.multiselect("Select students who are present", students, key="attendance_multiselect")

    if st.button("Submit Attendance"):
        if present_students:
            save_teacher_attendance(present_students)  # Ensure this function is defined
        else:
            st.warning("Please select at least one student.")

    # Option to view attendance records
    st.subheader("View Attendance Records")
    if st.button("Show Attendance Records"):
        try:
            conn = sqlite3.connect("attendance.db")
            cursor = conn.cursor()

            # Fetch all attendance records
            cursor.execute("SELECT date, student_name FROM attendance_records ORDER BY date DESC")
            attendance_records = cursor.fetchall()

            # Fetch all present today records
            cursor.execute("SELECT username, timestamp FROM present_today ORDER BY timestamp DESC")
            present_today_records = cursor.fetchall()
            conn.close()

            # Convert attendance records to a DataFrame
            if attendance_records:
                attendance_df = pd.DataFrame(attendance_records, columns=["Date", "Student Name"])
                st.write("### Attendance Records")
                st.write(attendance_df)
            else:
                st.info("No attendance records found.")

            # Convert present today records to a DataFrame
            if present_today_records:
                present_today_df = pd.DataFrame(present_today_records, columns=["Username", "Timestamp"])
                st.write("### Present Today Records")
                st.write(present_today_df)
            else:
                st.info("No present today records found.")

        except Exception as e:
            st.error(f"An error occurred while fetching attendance records: {e}")

    # Sidebar statistics (optional)
    st.subheader("Dashboard Statistics")
    total_students = len(students)
    attendance_rate = 89  # Placeholder

    col1, col2 = st.columns(2)
    with col1:
        st.metric(label="Total Students", value=f"{total_students}")
    with col2:
        st.metric(label="Attendance Rate", value=f"{attendance_rate}%")

# Database setup and login system
def init_db():
    """Initialize the unified database for all users."""
    conn = sqlite3.connect('users.db')  # Use a single database for both teachers and students
    cursor = conn.cursor()
    
    # Drop the users table if it exists (to reset schema)
    cursor.execute("DROP TABLE IF EXISTS users")
    
    # Recreate the users table with the correct schema
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            user_type TEXT NOT NULL  -- 'teacher' or 'student'
        )
    """)
    conn.commit()
    conn.close()
    print("Database initialized successfully!")


def add_user_to_db(username, password, role):
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        c.execute("INSERT INTO users (user_id, password_hash, user_type) VALUES (?, ?, ?)", (username, hashed_password, role))
        conn.commit()
        print(f"User '{username}' added successfully.")
    except sqlite3.IntegrityError:
        print(f"User '{username}' already exists.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        conn.close()


# Shared materials database setup
def init_materials_db():
    os.makedirs("uploaded_materials", exist_ok=True)  # Ensure the directory exists
    conn = sqlite3.connect("shared_materials.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            upload_time TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

# Fetch uploaded materials
def fetch_uploaded_materials():
    init_materials_db()  # Ensure the database is initialized
    conn = sqlite3.connect("shared_materials.db")
    cursor = conn.cursor()
    cursor.execute("SELECT filename, upload_time FROM materials ORDER BY upload_time DESC")
    materials = cursor.fetchall()
    conn.close()
    return materials

@st.cache_data
def load_default_timetable():
    # Sample timetable data
    data = {
        "Time": ["09-10 AM", "10-11 AM", "11-12 AM", "12-01 PM", "01-02 PM", "02-03 PM", "03-04 PM", "04-05 PM"],
        "Monday": ["Lecture / G:All C:PEV112 / R: 56-703 / S:BO301"] * 8,
        "Tuesday": ["Lecture / G:All C:PEV112 / R: 56-703 / S:BO301"] * 8,
        "Wednesday": ["Practical / G:1 C:PEV112 / R: 56-703 / S:BO301"] * 8,
        "Thursday": [""] * 8,
        "Friday": [""] * 8,
        "Saturday": [""] * 8
    }
    return pd.DataFrame(data)

def load_course_info():
    # Sample course information
    course_data = {
        "CourseCode": ["BTY396", "BTY416", "BTY441", "BTY463", "BTY464", "BTY496", "BTY499", "BTY651", "ICT202B", "PEA402", "PESS01", "PEV112"],
        "CourseType": ["CR", "CR", "EM", "CR", "CR", "CR", "CR", "PW", "CR", "OM", "PE", "OM"],
        "CourseName": ["BIOSEPARATION ENGINEERING", "BIOSEPARATION ENGINEERING LABORATORY", "PHARMACEUTICAL ENGINEERING", 
                       "BIOINFORMATICS AND COMPUTATIONAL BIOLOGY", "BIOINFORMATICS AND COMPUTATIONAL BIOLOGY LABORATORY", 
                       "METABOLIC ENGINEERING", "SEMINAR ON SUMMER TRAINING", "QUALITY CONTROL AND QUALITY ASSURANCE", 
                       "AI, ML AND EMERGING TECHNOLOGIES", "ANALYTICAL SKILLS -II", "MENTORING - VII", "VERBAL ABILITY"],
        "Credits": [3, 1, 3, 2, 1, 2, 3, 3, 2, 4, 0, 3],
        "Faculty": ["Dr. Ajay Kumar", "Dr. Ajay Kumar", "Dr. Shashank Garg", "Dr. Anish Kumar", 
                    "Dr. Anish Kumar", "Dr. Shashank Garg", "", "Dr. Aarti Bains", 
                    "Dr. Piyush Kumar Yadav", "Kamal Deep", "", "Jaskiranjit Kaur"]
    }
    return pd.DataFrame(course_data)


def mark_attendance(username):
    """Insert a new attendance record into the database."""
    try:
        conn = sqlite3.connect("attendance.db")
        cursor = conn.cursor()
        
        # Get the current timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Insert a new attendance record into the attendance_records table
        cursor.execute("INSERT INTO attendance_records (date, student_name) VALUES (?, ?)", (timestamp, username))
        
        conn.commit()
        st.success(f"Attendance marked successfully for {username} at {timestamp}!")
    except Exception as e:
        st.error(f"Failed to mark attendance: {e}")
    finally:
        conn.close()


def student_dashboard():
    st.sidebar.title("Navigation")
    page = st.sidebar.selectbox("Choose a page", ("Home", "Simulation", "Reading Material", "Questions", "Attendence"))
    
    

    # Logout button in the sidebar
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.pop('login_time', None)
        st.success("You have been logged out.")

    # Call the function to detect tab switches
    detect_tab_switch()
    
    if page == "Home":
        home()
    elif page == "Simulation":
        st.title("Simulation")
        display_flip_clock()
        display_session_timer()
        st.write("Implement simulations")
    elif page == "Reading Material":
        st.title("Reading Material")
        display_flip_clock()
        display_session_timer()
        st.write("Here are some flashcards/reading material to engage students.")
    elif page == "Questions":
        st.title("Questions")
        display_flip_clock()
        display_session_timer()
        st.write("Welcome to the Engaging Page.")
    elif page == "Attendence":
        st.title("YOUR Attendence")
        display_flip_clock()
        display_session_timer()
        Attendence()

    
def Attendence ():   
    st.title("Student Dashboard")
    init_present_today_db()
   # Ensure the login_time is timezone-aware
    if "login_time" not in st.session_state:
        user_timezone = pytz.timezone(get_user_timezone())
        st.session_state["login_time"] = datetime.now(user_timezone)

    # Get the current time in the user's timezone
    current_time = datetime.now(pytz.timezone(get_user_timezone()))

    # Calculate elapsed time
    elapsed_time = (current_time - st.session_state["login_time"]).total_seconds()

    # Display waiting information if less than 3 minutes
    if elapsed_time < 10:  # 3 minutes
        st.info(f"Please wait for {int(180 - elapsed_time)} seconds before entering the code.")
        st.stop()  # Stop the execution of the dashboard

    # Show the code input field after 3 minutes
    input_code = st.text_input("Enter the code provided by your teacher:")
    if st.button("Submit Code"):
        if validate_code(input_code):
            username = st.session_state["user_id"]
            mark_attendance(username)  # This will now create a new attendance record
        else:
            st.error("Invalid code. Please try again.")           

def home():
    st.title("Academic Schedule and Course Information")
    st.write("Welcome to the Home Page.")

    timetable_df = load_default_timetable()
    tab1, tab2, tab3 = st.tabs(["Weekly Schedule", "Course Information", "Learning Materials"])

    with tab1:
        st.subheader("Weekly Class Schedule")
        st.dataframe(timetable_df)

    with tab2:
        st.subheader("Course Information")
        course_info_df = load_course_info()
        st.dataframe(course_info_df)

    with tab3:
        st.subheader("Learning Materials")
        materials = fetch_uploaded_materials()
        if materials:
            for idx, (filename, upload_time) in enumerate(materials):
                st.markdown(f"**{filename}** uploaded on {upload_time}")
                file_path = os.path.join("uploaded_materials", filename)
                with open(file_path, "rb") as f:
                    # Add a unique key using filename and index
                    st.download_button(f"Download {filename}", f, file_name=filename, key=f"download-{idx}")
        else:
            st.info("No materials have been uploaded yet.")

def main():
    """Main function to route users to the appropriate dashboard based on their role."""
    if st.session_state.get("logged_in"):
        role = st.session_state["user_role"]
        if role == "teacher":
            professor_dashboard()  # Redirect to teacher dashboard
        elif role == "student":
            student_dashboard()  # Redirect to student dashboard
        else:
            st.error("Unknown role. Please contact the administrator.")
    else:
        login_page()


def app():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    main()

if __name__ == "__main__":
    app()



