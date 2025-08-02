import streamlit as st
from google_sheets_manager import get_users_df, get_shifts_df, get_assignments_df, generate_uuid, update_users_df, update_shifts_df, update_assignments_df, get_gspread_client, append_row, update_row, clear_cache, get_annual_leave_df, get_specialties_df, get_worksheet, delete_row
import pandas as pd
from ortools.sat.python import cp_model

def main():
    st.set_page_config(layout="wide")
    st.title("GP Surgery - Shift Scheduling App")
    st.sidebar.image("images/logo.png")

    # Initialize session state for dataframes if not already present
    if 'users_df' not in st.session_state:
        st.session_state.users_df = pd.DataFrame()
    if 'shifts_df' not in st.session_state:
        st.session_state.shifts_df = pd.DataFrame()
    if 'assignments_df' not in st.session_state:
        st.session_state.assignments_df = pd.DataFrame()
    if 'annual_leave_df' not in st.session_state:
        st.session_state.annual_leave_df = pd.DataFrame()
    if 'specialties_df' not in st.session_state:
        st.session_state.specialties_df = pd.DataFrame()
    if 'daily_staffing_req' not in st.session_state:
        st.session_state.daily_staffing_req = {}

    # Initialize Google Sheets client
    @st.cache_resource
    def get_cached_gspread_client():
        try:
            return get_gspread_client()
        except Exception as e:
            st.error(f"Google Sheets Authentication Error: {e}. Please check your Streamlit secrets configuration.")
            st.stop()

    # Load data from Google Sheets on app start or refresh
    try:
        # Ensure client is initialized before attempting to read data
        get_cached_gspread_client()
        st.session_state.users_df = get_users_df()
        st.session_state.shifts_df = get_shifts_df()
        st.session_state.assignments_df = get_assignments_df()
        st.session_state.annual_leave_df = get_annual_leave_df()
        st.session_state.specialties_df = get_specialties_df()
    except ValueError as e: # Catch specific errors from get_worksheet (e.g., unknown sheet name key)
        st.error(f"Data Loading Error: {e}. Please check your sheet names in google_sheets_manager.py.")
        st.stop()
    except Exception as e: # Catch any other general errors during data loading
        st.error(f"Data Loading Error: {e}. Please check your Google Sheet setup and data integrity.")
        st.stop()

    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["Dashboard", "User Management", "Shift Definition", "Shift Scheduling", "Annual Leave Management", "Constraint Management"])

    st.sidebar.markdown("---")
    if st.sidebar.button(":material/refresh: Reload Data"):
        clear_cache()
        st.success(":material/refresh: Data Reloaded Successfully!")
        st.rerun()

    if page == "Dashboard":
        st.header("Dashboard")
        st.write("Welcome to the GP Surgery Shift Scheduling Dashboard!")
        # Placeholder for dashboard content
        st.info("This section will display an overview of schedules and key metrics.")

    elif page == "User Management":
        st.header("User Management")
        st.write("Manage your staff members here.")

        st.subheader("Current Users")
        if not st.session_state.users_df.empty:
            st.dataframe(st.session_state.users_df)
        else:
            st.info("No users found. Please add new users or upload a CSV.")

        st.subheader("Add New User")
        with st.form("add_user_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Name", key="new_user_name")
                email = st.text_input("Email", key="new_user_email")
                start_date = st.date_input("Start Date", key="new_user_start_date")
                role = st.selectbox("Role", ["GP Partner", "Salaried GP", "Nurse", "HCA", "Receptionist", "Practice Manager", "Administrator", "Other"], key="new_user_role")
                contract_type = st.selectbox("Contract Type", ["Full-time", "Part-time", "Locum"], key="new_user_contract_type")
                skills = st.multiselect("Skills/Qualifications", st.session_state.specialties_df['skills'].tolist() if not st.session_state.specialties_df.empty else [], key="new_user_skills")
            with col2:
                annual_leave_total_days = st.number_input("Annual Leave (Total Days)", min_value=0, value=25, key="new_user_annual_leave_total_days")
                sessions_per_day_limit = st.number_input("Sessions Per Day Limit", min_value=0, value=2, key="new_user_sessions_per_day_limit")
                preferred_days_off = st.multiselect("Preferred Days Off", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"], key="new_user_preferred_days_off")

            submitted = st.form_submit_button("Add User")
            if submitted:
                if name and email and start_date and role:
                    new_user_data = {
                        "user_id": generate_uuid(),
                        "name": name,
                        "email": email,
                        "start_date": str(start_date),
                        "annual_leave_total_days": annual_leave_total_days,
                        "annual_leave_taken_days": 0, # Always start with 0 taken
                        "role": role,
                        "contract_type": contract_type,
                        "skills": skills,
                        "sessions_per_day_limit": sessions_per_day_limit,
                        "preferred_day_off": ", ".join(preferred_days_off) if isinstance(preferred_days_off, list) else preferred_days_off,
                        "availability": "{}" # Placeholder for future complex availability
                    }
                    # Get the header row from the Google Sheet to ensure correct order
                    worksheet = get_worksheet("Users")
                    header = worksheet.row_values(1)

                    # Create a new DataFrame with the correct column order
                    new_user_df = pd.DataFrame([new_user_data], columns=header)

                    # Replace NaN with None for JSON compatibility
                    new_user_df = new_user_df.astype(object).where(pd.notnull(new_user_df), None)

                    # Convert the DataFrame row to a list and append to the sheet
                    append_row("Users", new_user_df.values.tolist()[0])

                    clear_cache()
                    st.success(f"User '{name}' added successfully!")
                    st.rerun() # Rerun to update the dataframe display
                else:
                    st.error("Please fill in all required fields (Name, Email, Start Date, Role).")

        st.subheader("Upload Users from CSV")

        # Create a template for download
        user_template_df = pd.DataFrame({
            'name': ['John Doe'],
            'email': ['john.doe@example.com'],
            'start_date': ['2024-01-01'],
            'role': ['GP'],
            'contract_type': ['Full-time'],
            'skills': [[]],
            'annual_leave_total_days': [25],
            'sessions_per_day_limit': [2],
            'preferred_day_off': ['None']
        })
        user_template_csv = user_template_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download User CSV Template",
            data=user_template_csv,
            file_name='user_template.csv',
            mime='text/csv',
        )

        with st.form("user_csv_upload_form", clear_on_submit=True):
            uploaded_file = st.file_uploader("Choose a CSV file", type="csv")
            submitted = st.form_submit_button("Upload CSV")

            if submitted and uploaded_file is not None:
                with st.spinner("Uploading CSV, please wait..."):
                    try:
                        csv_df = pd.read_csv(uploaded_file)
                        # Replace NaN with None for JSON compatibility
                        csv_df = csv_df.astype(object).where(pd.notnull(csv_df), None)
                        # Ensure user_id is present or generate if missing
                        if 'user_id' not in csv_df.columns:
                            csv_df['user_id'] = [generate_uuid() for _ in range(len(csv_df))]
                        # Ensure other columns exist with default values if not present
                        for col in ["annual_leave_taken_days", "sessions_per_day_limit", "days_per_week_limit", "preferred_day_off", "availability"]:
                            if col not in csv_df.columns:
                                if col == "annual_leave_taken_days":
                                    csv_df[col] = 0
                                elif col == "sessions_per_day_limit":
                                    csv_df[col] = 2
                                elif col == "preferred_day_off":
                                    csv_df[col] = "None"
                                elif col == "availability":
                                    csv_df[col] = "{}"

                        # Reorder columns to match the Google Sheet
                        sheet_columns = get_worksheet("Users").row_values(1)
                        csv_df = csv_df.reindex(columns=sheet_columns)

                        for _, row in csv_df.iterrows():
                            append_row("Users", row.tolist())
                        clear_cache()
                        st.success("Users uploaded successfully from CSV!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error uploading CSV: {e}")

        st.subheader("Edit User")
        if not st.session_state.users_df.empty:
            user_to_edit_name = st.selectbox("Select User to Edit", st.session_state.users_df['name'].tolist())
            if user_to_edit_name:
                user_to_edit = st.session_state.users_df[st.session_state.users_df['name'] == user_to_edit_name].iloc[0].to_dict()
                with st.form("edit_user_form", clear_on_submit=True):
                    col1, col2 = st.columns(2)
                    with col1:
                        name = st.text_input("Name", value=user_to_edit['name'], key="edit_user_name")
                        email = st.text_input("Email", value=user_to_edit['email'], key="edit_user_email")
                        start_date = st.date_input("Start Date", value=pd.to_datetime(user_to_edit['start_date']), key="edit_user_start_date")
                        role = st.selectbox("Role", ["GP Partner", "Salaried GP", "Nurse", "HCA", "Receptionist", "Practice Manager", "Administrator", "Clinical Pharmacist", "Other"], index=["GP Partner", "Salaried GP", "Nurse", "HCA", "Receptionist", "Practice Manager", "Administrator", "Clinical Pharmacist", "Other"].index(user_to_edit['role']), key="edit_user_role")
                        contract_type = st.selectbox("Contract Type", ["Full-time", "Part-time", "Locum"], index=["Full-time", "Part-time", "Locum"].index(user_to_edit.get('contract_type', 'Full-time')), key="edit_user_contract_type")
                        skills = st.multiselect("Skills/Qualifications", st.session_state.specialties_df['skills'].tolist() if not st.session_state.specialties_df.empty else [], default=[s.strip() for s in user_to_edit.get('skills', '').split(',') if s.strip()], key="edit_user_skills")
                    with col2:
                        annual_leave_total_days = st.number_input("Annual Leave (Total Days)", min_value=0, value=user_to_edit['annual_leave_total_days'], key="edit_user_annual_leave_total_days")
                        sessions_per_day_limit = st.number_input("Sessions Per Day Limit", min_value=0, value=user_to_edit['sessions_per_day_limit'], key="edit_user_sessions_per_day_limit")
                        preferred_days_off = st.multiselect("Preferred Days Off", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"], default=[d.strip() for d in user_to_edit.get('preferred_day_off', '').split(',') if d.strip()], key="edit_user_preferred_days_off")

                    submitted = st.form_submit_button("Update User")
                    if submitted:
                        updated_user_data = {
                            "user_id": user_to_edit['user_id'],
                            "name": name,
                            "email": email,
                            "start_date": str(start_date),
                            "annual_leave_total_days": annual_leave_total_days,
                            "annual_leave_taken_days": user_to_edit['annual_leave_taken_days'], # This should be updated separately
                            "role": role,
                            "contract_type": contract_type,
                            "skills": skills,
                            "sessions_per_day_limit": sessions_per_day_limit,
                            "preferred_day_off": ", ".join(preferred_days_off) if isinstance(preferred_days_off, list) else preferred_days_off,
                            "availability": user_to_edit['availability'] # This should be updated separately
                        }
                        update_row("Users", user_to_edit['user_id'], updated_user_data)
                        clear_cache()
                        st.success(f"User '{name}' updated successfully!")
                        st.rerun()
        else:
            st.info("No users to edit.")

        st.subheader("Delete User")
        if not st.session_state.users_df.empty:
            user_to_delete_name = st.selectbox("Select User to Delete", st.session_state.users_df['name'].tolist(), key="delete_user_select")
            if user_to_delete_name:
                st.warning(f"You are about to delete {user_to_delete_name}. This action cannot be undone.")
                user_to_delete_id = st.session_state.users_df[st.session_state.users_df['name'] == user_to_delete_name]['user_id'].iloc[0]
                if st.button("Confirm Delete User", key="delete_user_confirm_button"):
                    delete_row("Users", user_to_delete_id)
                    clear_cache()
                    st.success(f"User '{user_to_delete_name}' deleted successfully!")
                    st.rerun()
        else:
            st.info("No users to delete.")

    elif page == "Shift Definition":
        st.header("Shift Definition")
        st.write("Define and manage different shift types.")

        st.subheader("Current Shifts")
        if not st.session_state.shifts_df.empty:
            # Display base_shift_name and session_type directly
            display_shifts_df = st.session_state.shifts_df.copy()
            # Remove the constructed 'shift_name' column for display if it exists
            if 'shift_name' in display_shifts_df.columns:
                display_shifts_df.drop(columns=['shift_name'], inplace=True)
            st.dataframe(display_shifts_df)
        else:
            st.info("No shifts defined yet. Please add new shifts.")

        st.subheader("Add New Shift")
        with st.form("add_shift_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                base_shift_name = st.text_input("Base Shift Name", key="new_shift_name_base")
                session_type = st.selectbox("Session Type", ["AM", "PM", "None"], key="new_shift_session_type")
                start_time = st.time_input("Start Time", value=pd.to_datetime("08:00").time(), key="new_shift_start_time")
                end_time = st.time_input("End Time", value=pd.to_datetime("12:10").time(), key="new_shift_end_time")
            with col2:
                required_role = st.selectbox("Required Role", ["GP Partner", "Salaried GP", "Nurse", "HCA", "Receptionist", "Practice Manager", "Administrator", "Clinical Pharmacist", "Any"], key="new_shift_required_role")
                capacity = st.number_input("Capacity (Number of Staff)", min_value=1, value=1, key="new_shift_capacity")
                is_admin_slot = st.toggle("Is Admin Slot?", value=False, key="new_shift_is_admin_slot")
                is_remote = st.toggle("Is Remote?", value=False, key="new_shift_is_remote")
                skills_required = st.multiselect("Skills Required", st.session_state.specialties_df['skills'].tolist() if not st.session_state.specialties_df.empty else [], key="new_shift_skills_required")
                required_days = st.multiselect("Required Days of the Week", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"], key="new_shift_required_days")

            submitted = st.form_submit_button("Add Shift")
            if submitted:
                if base_shift_name and start_time and end_time and required_role:
                    # Format base_shift_name for storage (lowercase, hyphens)
                    formatted_base_shift_name = str(base_shift_name).lower().replace(' ', '-')
                    session_type_str = str(session_type)

                    # Construct the full shift_name for the 'shift_name' column in Google Sheet
                    # This will be used for display purposes in some parts of the app
                    formatted_shift_name = f"{formatted_base_shift_name}-{session_type_str.lower()}" if session_type_str in ["AM", "PM"] else formatted_base_shift_name
                    new_shift_data = {
                        "shift_id": generate_uuid(),
                        "shift_name": formatted_shift_name, # Combined name for display
                        "base_shift_name": formatted_base_shift_name, # New column for base name
                        "session_type": session_type_str, # New column for AM/PM
                        "start_time": str(start_time),
                        "end_time": str(end_time),
                        "required_role": required_role,
                        "capacity": capacity,
                        "is_admin_slot": is_admin_slot,
                        "is_remote": is_remote,
                        "skills_required": ", ".join(skills_required) if isinstance(skills_required, list) else skills_required,
                        "required_days": ", ".join(required_days) if isinstance(required_days, list) else required_days
                    }
                    # Get the header row from the Google Sheet to ensure correct order
                    worksheet = get_worksheet("Shifts")
                    header = worksheet.row_values(1)

                    # Create a new DataFrame with the correct column order
                    new_shift_df = pd.DataFrame([new_shift_data], columns=header)

                    # Replace NaN with None for JSON compatibility
                    new_shift_df = new_shift_df.astype(object).where(pd.notnull(new_shift_df), None)

                    # Convert the DataFrame row to a list and append to the sheet
                    append_row("Shifts", new_shift_df.values.tolist()[0])

                    clear_cache()
                    st.success(f"Shift '{formatted_shift_name}' added successfully!")
                    st.rerun()
                else:
                    st.error("Please fill in all required fields (Shift Name, Start Time, End Time, Required Role).")

        st.subheader("Upload Shifts from CSV")
        # Create a template for download
        shift_template_df = pd.DataFrame({
            'shift_name': ['Morning Clinic'],
            'start_time': ['08:00'],
            'end_time': ['12:10'],
            'required_role': ['GP'],
            'capacity': [1],
            'is_admin_slot': [False],
            'is_remote': [False],
            'skills_required': [[]],
            'required_days': [["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]]
        })
        shift_template_csv = shift_template_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download Shift CSV Template",
            data=shift_template_csv,
            file_name='shift_template.csv',
            mime='text/csv',
        )

        with st.form("shift_csv_upload_form", clear_on_submit=True):
            uploaded_shift_file = st.file_uploader("Choose a CSV file", type="csv")
            submitted = st.form_submit_button("Upload CSV")

            if submitted and uploaded_shift_file is not None:
                with st.spinner("Uploading CSV, please wait..."):
                    try:
                        csv_df = pd.read_csv(uploaded_shift_file)
                        # Replace NaN with None for JSON compatibility
                        csv_df = csv_df.astype(object).where(pd.notnull(csv_df), None)
                        # Ensure shift_id is present or generate if missing
                        if 'shift_id' not in csv_df.columns:
                            csv_df['shift_id'] = [generate_uuid() for _ in range(len(csv_df))]

                        for _, row in csv_df.iterrows():
                            append_row("Shifts", row.tolist())
                        clear_cache()
                        st.success("Shifts uploaded successfully from CSV!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error uploading CSV: {e}")

        st.subheader("Edit Shift")
        if not st.session_state.shifts_df.empty:
            # Use base_shift_name for selection display
            # Ensure 'base_shift_name' column exists before trying to access it
            if 'base_shift_name' not in st.session_state.shifts_df.columns:
                st.error("The 'base_shift_name' column is missing from your Shifts data. Please ensure your Google Sheet is configured correctly.")
                return

            shift_to_edit_base_name_display = st.selectbox("Select Shift to Edit", st.session_state.shifts_df['base_shift_name'].tolist())
            if shift_to_edit_base_name_display:
                # Find the shift using base_shift_name
                shift_to_edit = st.session_state.shifts_df[st.session_state.shifts_df['base_shift_name'] == shift_to_edit_base_name_display].iloc[0].to_dict()

                # Read base_shift_name and session_type directly from the loaded shift
                initial_base_shift_name = shift_to_edit.get('base_shift_name', '')
                initial_session_type = shift_to_edit.get('session_type', 'None')

                # Determine the index for the session_type selectbox
                session_type_options = ["AM", "PM", "None"]
                try:
                    selected_session_type_index = session_type_options.index(initial_session_type)
                except ValueError:
                    selected_session_type_index = session_type_options.index("None") # Default to None if not found

                with st.form("edit_shift_form", clear_on_submit=True):
                    col1, col2 = st.columns(2)
                    with col1:
                        base_shift_name = st.text_input("Base Shift Name", value=initial_base_shift_name, key="edit_shift_name_base")
                        session_type = st.selectbox("Session Type", session_type_options, index=selected_session_type_index, key="edit_shift_session_type")
                        start_time = st.time_input("Start Time", value=pd.to_datetime(shift_to_edit['start_time']).time(), key="edit_shift_start_time")
                        end_time = st.time_input("End Time", value=pd.to_datetime(shift_to_edit['end_time']).time(), key="edit_shift_end_time")
                    with col2:
                        shift_roles = ["GP Partner", "Salaried GP", "Nurse", "HCA", "Receptionist", "Practice Manager", "Administrator", "Clinical Pharmacist", "Any"]
                        current_shift_role = shift_to_edit.get('required_role')
                        try:
                            shift_role_index = shift_roles.index(current_shift_role)
                        except ValueError:
                            shift_role_index = shift_roles.index("Any") # Default to 'Any'
                        required_role = st.selectbox("Required Role", shift_roles, index=shift_role_index, key="edit_shift_required_role")
                        capacity = st.number_input("Capacity (Number of Staff)", min_value=1, value=shift_to_edit['capacity'], key="edit_shift_capacity")
                        is_admin_slot = st.toggle("Is Admin Slot?", value=shift_to_edit.get('is_admin_slot', False), key="edit_shift_is_admin_slot")
                        is_remote = st.toggle("Is Remote?", value=shift_to_edit.get('is_remote', False), key="edit_shift_is_remote")
                        skills_required = st.multiselect("Skills Required", st.session_state.specialties_df['skills'].tolist() if not st.session_state.specialties_df.empty else [], default=[s.strip() for s in shift_to_edit.get('skills_required', '').split(',') if s.strip()], key="edit_shift_skills_required")
                        required_days = st.multiselect("Required Days of the Week", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"], default=[d.strip() for d in shift_to_edit.get('required_days', '').split(',') if d.strip()], key="edit_shift_required_days")

                    submitted = st.form_submit_button("Update Shift")
                    if submitted:
                        # Format base_shift_name for storage (lowercase, hyphens)
                        formatted_base_shift_name = str(base_shift_name).lower().replace(' ', '-')
                        session_type_str = str(session_type)

                        # Construct the full shift_name for the 'shift_name' column in Google Sheet
                        formatted_shift_name = f"{formatted_base_shift_name}-{session_type_str.lower()}" if session_type_str in ["AM", "PM"] else formatted_base_shift_name
                        updated_shift_data = {
                            "shift_id": shift_to_edit['shift_id'],
                            "shift_name": formatted_shift_name, # Combined name for display
                            "base_shift_name": formatted_base_shift_name, # New column for base name
                            "session_type": session_type_str, # New column for AM/PM
                            "start_time": str(start_time),
                            "end_time": str(end_time),
                            "required_role": required_role,
                            "capacity": capacity,
                            "is_admin_slot": is_admin_slot,
                            "is_remote": is_remote,
                            "skills_required": ", ".join(skills_required) if isinstance(skills_required, list) else skills_required,
                            "required_days": ", ".join(required_days) if isinstance(required_days, list) else required_days
                        }
                        update_row("Shifts", shift_to_edit['shift_id'], updated_shift_data)
                        clear_cache()
                        st.success(f"Shift '{formatted_shift_name}' updated successfully!")
                        st.rerun()
        else:
            st.info("No shifts to edit.")

        st.subheader("Delete Shift")
        if not st.session_state.shifts_df.empty:
            shift_to_delete_base_name_display = st.selectbox("Select Shift to Delete", st.session_state.shifts_df['base_shift_name'].tolist(), key="delete_shift_name")
            if shift_to_delete_base_name_display:
                shift_to_delete_id = st.session_state.shifts_df[st.session_state.shifts_df['base_shift_name'] == shift_to_delete_base_name_display]['shift_id'].iloc[0]
                if st.button("Delete Shift", key="delete_shift_button"):
                    delete_row("Shifts", shift_to_delete_id)
                    clear_cache()
                    st.success(f"Shift '{shift_to_delete_base_name_display}' deleted successfully!")
                    st.rerun()
        else:
            st.info("No shifts to delete.")

    elif page == "Shift Scheduling":
        st.header("Shift Scheduling")
        st.write("Generate and manage shift assignments.")

        st.subheader("Schedule Generation")
        col1, col2 = st.columns(2)
        with col1:
            schedule_start_date = st.date_input("Schedule Start Date", value=pd.to_datetime("today"), key="schedule_start_date")
        with col2:
            num_days_to_schedule = st.number_input("Number of Days to Schedule", min_value=1, value=7, key="num_days_to_schedule")

        if st.button("Generate Schedule"):
            if st.session_state.users_df.empty or st.session_state.shifts_df.empty:
                st.warning("Please add users and define shifts before generating a schedule.")
            else:
                with st.spinner("Generating schedule... This may take a moment."):
                    from shift_solver import solve_shift_scheduling
                    assigned_df, status, reason = solve_shift_scheduling(
                        st.session_state.users_df,
                        st.session_state.shifts_df,
                        schedule_start_date,
                        num_days_to_schedule,
                        st.session_state.daily_staffing_req
                    )

                    # Display results or reason for failure
                    if assigned_df is not None and not assigned_df.empty:
                        st.success("Schedule generated successfully!")
                        st.subheader("Generated Schedule Overview")

                        # Merge with user and shift names for better readability
                        display_df = assigned_df.merge(st.session_state.users_df[['user_id', 'name', 'role']], on='user_id', how='left')
                        display_df = display_df.merge(st.session_state.shifts_df[['shift_id', 'base_shift_name', 'session_type', 'start_time', 'end_time']], on='shift_id', how='left')

                        # Sort for better display
                        display_df['date'] = pd.to_datetime(display_df['date'])
                        display_df['Day of the Week'] = display_df['date'].dt.day_name()
                        display_df = display_df.sort_values(by=['date', 'role', 'start_time', 'base_shift_name'])

                        st.dataframe(display_df[['date', 'Day of the Week', 'base_shift_name', 'session_type', 'start_time', 'end_time', 'name', 'role', 'type']])

                        # Plot staffing levels over time
                        st.subheader("Staffing Levels Over Time")
                        staffing_counts = display_df.groupby('date').size().reset_index(name='staff_count')

                        import plotly.express as px
                        fig = px.line(staffing_counts, x='date', y='staff_count', title='Total Staff Assigned Per Day')
                        st.plotly_chart(fig, use_container_width=True)

                        st.subheader("Staffing Levels by Role Over Time")
                        staffing_by_role = display_df.groupby(['date', 'role']).size().reset_index(name='staff_count')
                        fig_role = px.bar(staffing_by_role, x='date', y='staff_count', color='role', title='Staff Assigned Per Role Per Day', barmode='stack')
                        st.plotly_chart(fig_role, use_container_width=True)

                        st.subheader("User Schedule Summary")
                        if not display_df.empty:
                            assigned_users = display_df['name'].unique()
                            for user_name in assigned_users:
                                st.markdown(f"**{user_name}**")
                                user_shifts = display_df[display_df['name'] == user_name]
                                for _, shift_row in user_shifts.iterrows():
                                    st.write(f"- {shift_row['Day of the Week']}, {shift_row['date'].strftime('%Y-%m-%d')}: {shift_row['base_shift_name']} ({shift_row['session_type']})")
                        else:
                            st.info("No users were assigned to any shifts.")

                        # Optionally, save to Google Sheet
                        if st.button("Save Generated Schedule to Google Sheet"):
                            for _, row in assigned_df.iterrows():
                                append_row("Assignments", row.tolist())
                            clear_cache()
                            st.success("Schedule saved to Assignments sheet!")
                            st.rerun()

                    elif status == cp_model.FEASIBLE or status == cp_model.OPTIMAL:
                        st.warning("Feasible solution found, but no shifts were assigned. This could be due to:")
                        st.markdown("- **Shift Requirements:** No shifts are defined for the selected date range (check 'Required Days of the Week' in Shift Definition).")
                        st.markdown("- **Staff Availability:** No staff members are available or meet the criteria for any defined shifts.")
                    else:
                        st.error(f"Schedule generation failed: {reason}")

        st.subheader("Current Assignments (from Google Sheet)")
        if not st.session_state.assignments_df.empty:
            # Merge with user and shift names for better readability
            display_assignments_df = st.session_state.assignments_df.merge(st.session_state.users_df[['user_id', 'name', 'role']], on='user_id', how='left')
            # Merge with base_shift_name and session_type for display
            display_assignments_df = display_assignments_df.merge(st.session_state.shifts_df[['shift_id', 'base_shift_name', 'session_type', 'start_time', 'end_time']], on='shift_id', how='left')
            display_assignments_df['date'] = pd.to_datetime(display_assignments_df['date'])
            display_assignments_df['Day of the Week'] = display_assignments_df['date'].dt.day_name()
            display_assignments_df = display_assignments_df.sort_values(by=['date', 'role', 'start_time', 'base_shift_name'])
            st.dataframe(display_assignments_df[['date', 'Day of the Week', 'base_shift_name', 'session_type', 'start_time', 'end_time', 'name', 'role', 'type', 'status']])
        else:
            st.info("No assignments found in the Google Sheet.")

    elif page == "Annual Leave Management":
        st.header("Annual Leave Management")
        st.write("Manage staff annual leave requests.")

        st.subheader("Request Annual Leave")
        with st.form("request_annual_leave_form", clear_on_submit=True):
            user_name = st.selectbox("Select User", st.session_state.users_df['name'].tolist(), key="leave_user_name")
            start_date = st.date_input("Start Date", key="leave_start_date")
            end_date = st.date_input("End Date", key="leave_end_date")
            reason = st.text_area("Reason for Leave", key="leave_reason")

            submitted = st.form_submit_button("Submit Leave Request")
            if submitted:
                if user_name and start_date and end_date and reason:
                    # Find user_id from user_name
                    user_id = st.session_state.users_df[st.session_state.users_df['name'] == user_name]['user_id'].iloc[0]

                    new_leave_request = {
                        "leave_id": generate_uuid(),
                        "user_id": user_id,
                        "user_name": user_name,
                        "start_date": str(start_date),
                        "end_date": str(end_date),
                        "reason": reason,
                        "status": "Pending" # Initial status
                    }
                    append_row("Annual_Leave", list(new_leave_request.values()))
                    clear_cache()
                    st.success(f"Annual leave request for {user_name} from {start_date} to {end_date} submitted successfully!")
                    st.rerun()
                else:
                    st.error("Please fill in all required fields for the leave request.")

        st.subheader("Current Annual Leave Requests")
        # Fetch annual leave data (assuming a new sheet named "Annual_Leave")
        try:
            if not st.session_state.annual_leave_df.empty:
                st.dataframe(st.session_state.annual_leave_df)
            else:
                st.info("No annual leave requests found.")
        except Exception as e:
            st.warning(f"Could not load annual leave data. Please ensure 'Annual_Leave' sheet exists and is configured. Error: {e}")

    elif page == "Constraint Management":
        st.header("Constraint Management")
        st.write("Define and manage scheduling constraints.")

        st.subheader("Common Constraints (from User and Shift Definitions)")
        st.info("These constraints are defined in the User Management and Shift Definition sections.")
        st.write("User-specific limits (sessions/day, days/week, preferred day off):")
        if not st.session_state.users_df.empty:
            st.dataframe(st.session_state.users_df[['name', 'sessions_per_day_limit', 'preferred_day_off']])
        else:
            st.info("No users defined to display constraints.")

        st.write("Shift-specific properties (required role, capacity, admin slot):")
        if not st.session_state.shifts_df.empty:
            st.dataframe(st.session_state.shifts_df[['shift_name', 'required_role', 'capacity', 'is_admin_slot']])
        else:
            st.info("No shifts defined to display constraints.")

        st.subheader("Dynamic Constraint Builder")
        st.info("This section will allow you to build custom constraints using a user-friendly interface.")
        # Placeholder for dynamic constraint builder UI
        st.write("Coming Soon: UI to define constraints like 'Staff A cannot work with Staff B', 'Staff C must work on Tuesdays', etc.")

        st.subheader("Daily Staffing Requirements")
        st.write("Define the minimum number of staff required for each role on each day of the week.")

        roles = ["GP Partner", "Salaried GP", "Nurse", "HCA", "Receptionist", "Practice Manager", "Administrator", "Clinical Pharmacist", "Any"]
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        # Initialize or update the session state with all roles
        for role in roles:
            if role not in st.session_state.daily_staffing_req:
                st.session_state.daily_staffing_req[role] = {day: 0 for day in days}

        # Create the input grid
        for role in roles:
            st.markdown(f"**{role}**")
            cols = st.columns(len(days))
            for i, day in enumerate(days):
                with cols[i]:
                    st.session_state.daily_staffing_req[role][day] = st.number_input(
                        day,
                        min_value=0,
                        value=st.session_state.daily_staffing_req[role][day],
                        key=f"staff_req_{role}_{day}",
                        label_visibility="collapsed"
                    )

        st.subheader("Advanced Custom Code Constraints")
        st.info("For advanced users: write Python code to add custom constraints directly to the OR-Tools model.")
        custom_constraint_code = st.text_area(
            "Enter Python code for custom constraints here:",
            "def add_custom_constraints(model, assigned, staff_ids, dates, shift_ids):\n    # Example: Ensure 'Shuman' does not work on '2025-08-05'\n    # if 'user1' in staff_ids:\n    #     shuman_id = 'user1'\n    #     target_date = pd.to_datetime('2025-08-05').date()\n    #     if target_date in dates:\n    #         for sh_id in shift_ids:\n    #             model.Add(assigned[(shuman_id, target_date, sh_id)] == 0)\n    pass",
            height=300,
            key="custom_constraint_code"
        )
        st.warning("Use this feature with caution. Incorrect code can lead to errors or infeasible solutions.")
        st.write("The code entered here will be executed and passed to the OR-Tools model. You will have access to `model`, `assigned` variables, `staff_ids`, `dates`, and `shift_ids`.")
        # This code will need to be executed dynamically and passed to the solver.
        # This is a security risk and needs careful handling.
        # For now, it's a text area, the execution logic will be added later.

if __name__ == "__main__":
    main()
