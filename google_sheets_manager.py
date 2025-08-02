import gspread
import pandas as pd
import uuid
import streamlit as st # Import streamlit
from google.oauth2.service_account import Credentials

# Google Sheet details
SPREADSHEET_ID = "1k_B8YJGT7KxgMRaBmgwKAdqsWmCWmz3X2Fcj8xcs_Cc"
SHEET_NAME_USERS = "Sheet1"
SHEET_NAME_SHIFTS = "Sheet2"
SHEET_NAME_ASSIGNMENTS = "Sheet3"
SHEET_NAME_ANNUAL_LEAVE = "Sheet4"
SHEET_NAME_SPECIALTIES = "Sheet5"
SHEET_NAME_GENERATED_SCHEDULES = "Sheet3" # Adding Sheet3 for generated schedules

# Authenticate with Google Sheets using st.secrets
def get_gspread_client():
    try:
        creds = Credentials.from_service_account_info(
            st.secrets["gsheets"],
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        raise Exception(f"Error authenticating with Google Sheets: {e}")

def get_worksheet(sheet_name_key):
    """
    Returns a specific worksheet from the spreadsheet based on a logical name key.
    Maps logical names (Users, Shifts, Assignments) to actual sheet names (Sheet1, Sheet2, Sheet3).
    """
    client = get_gspread_client() # Get client directly

    # Map logical sheet names to actual sheet names
    sheet_name_map = {
        "Users": SHEET_NAME_USERS,
        "Shifts": SHEET_NAME_SHIFTS,
        "Assignments": SHEET_NAME_ASSIGNMENTS,
        "Annual_Leave": SHEET_NAME_ANNUAL_LEAVE,
        "Specialties": SHEET_NAME_SPECIALTIES,
        "Generated_Schedules": SHEET_NAME_GENERATED_SCHEDULES # Map new logical name
    }
    actual_sheet_name = sheet_name_map.get(sheet_name_key)

    if not actual_sheet_name:
        raise ValueError(f"Unknown logical sheet name key: {sheet_name_key}")

    try:
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        worksheet = spreadsheet.worksheet(actual_sheet_name)
        return worksheet
    except gspread.exceptions.SpreadsheetNotFound:
        raise gspread.exceptions.SpreadsheetNotFound(f"Spreadsheet with ID '{SPREADSHEET_ID}' not found.")
    except gspread.exceptions.WorksheetNotFound:
        raise gspread.exceptions.WorksheetNotFound(f"Worksheet '{actual_sheet_name}' not found in spreadsheet '{SPREADSHEET_ID}'.")
    except Exception as e:
        raise Exception(f"Error accessing worksheet '{actual_sheet_name}': {e}")

def read_data(sheet_name):
    """Reads all data from a specified worksheet into a pandas DataFrame."""
    worksheet = get_worksheet(sheet_name)
    if worksheet:
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        return df
    return pd.DataFrame()

def write_data(sheet_name, df):
    """Writes a pandas DataFrame to a specified worksheet, overwriting existing content."""
    worksheet = get_worksheet(sheet_name)
    if worksheet:
        # Clear existing content and write new data
        worksheet.clear()
        worksheet.update([df.columns.values.tolist()] + df.values.tolist())
        return True
    return False

def update_row(sheet_name, row_id, data):
    """Updates a single row in the specified worksheet identified by its ID."""
    worksheet = get_worksheet(sheet_name)
    if worksheet:
        # Get all data from the sheet to find the row index
        all_data = worksheet.get_all_records()
        df = pd.DataFrame(all_data)

        # Find the index of the row to update
        if 'user_id' in df.columns:
            row_index = df[df['user_id'] == row_id].index
        elif 'shift_id' in df.columns:
            row_index = df[df['shift_id'] == row_id].index
        elif 'assignment_id' in df.columns:
            row_index = df[df['assignment_id'] == row_id].index
        else:
            return False # No ID column found

        if not row_index.empty:
            # gspread rows are 1-based, and there's a header row
            sheet_row_index = row_index[0] + 2

            # Prepare the values in the correct order
            header = worksheet.row_values(1)
            update_values = [data.get(h) for h in header]

            # Create a list of gspread.cell.Cell objects to update
            cells_to_update = []
            for i, value in enumerate(update_values):
                if value is not None: # Only update cells with new values
                    cells_to_update.append(gspread.cell.Cell(sheet_row_index, i + 1, value))

            if cells_to_update:
                worksheet.update_cells(cells_to_update)
            return True
    return False

def append_row(sheet_name, row_data):
    """Appends a single row to the specified worksheet."""
    worksheet = get_worksheet(sheet_name)
    if worksheet:
        worksheet.append_row(row_data)
        return True
    return False

def delete_row(sheet_name, row_id):
    """Deletes a single row from the specified worksheet identified by its ID."""
    worksheet = get_worksheet(sheet_name)
    if worksheet:
        all_data = worksheet.get_all_records()
        df = pd.DataFrame(all_data)

        id_column = None
        if 'user_id' in df.columns:
            id_column = 'user_id'
        elif 'shift_id' in df.columns:
            id_column = 'shift_id'
        elif 'assignment_id' in df.columns:
            id_column = 'assignment_id'
        elif 'leave_id' in df.columns: # Added for annual leave
            id_column = 'leave_id'
        else:
            st.error(f"No identifiable ID column found for sheet '{sheet_name}'.")
            return False

        if id_column:
            row_index = df[df[id_column] == row_id].index
            if not row_index.empty:
                # gspread rows are 1-based, and there's a header row
                sheet_row_index = int(row_index[0]) + 2
                worksheet.delete_rows(sheet_row_index)
                return True
            else:
                st.warning(f"Row with ID '{row_id}' not found in sheet '{sheet_name}'.")
                return False
    return False

def clear_cache():
    st.cache_data.clear()

# --- Helper functions for specific sheets ---

@st.cache_data
def get_users_df():
    """Reads the Users sheet and returns a DataFrame."""
    return read_data("Users")

def update_users_df(df):
    """Writes the Users DataFrame back to the Users sheet."""
    for _, row in df.iterrows():
        update_row("Users", row['user_id'], row.to_dict())
    return True

@st.cache_data
def get_shifts_df():
    """
    Reads the Shifts sheet and returns a DataFrame.
    Constructs 'shift_name' from 'base_shift_name' and 'session_type'.
    """
    df = read_data("Shifts")
    if not df.empty:
        # Ensure 'base_shift_name' and 'session_type' columns exist
        # Assuming 'shift_name' column in Google Sheet is now 'base_shift_name'
        if 'shift_name' in df.columns:
            df.rename(columns={'shift_name': 'base_shift_name'}, inplace=True)
        if 'base_shift_name' not in df.columns:
            df['base_shift_name'] = '' # Default empty string

        if 'session_type' not in df.columns:
            df['session_type'] = 'AM' # Default to AM

        # Construct the combined 'shift_name' for internal use
        # Format: base-name-am/pm
        df['shift_name'] = df.apply(
            lambda row: f"{row['base_shift_name'].lower().replace(' ', '-')}-{row['session_type'].lower()}"
            if row['session_type'] in ['AM', 'PM'] else row['base_shift_name'].lower().replace(' ', '-'),
            axis=1
        )
    return df

def update_shifts_df(df):
    """
    Writes the Shifts DataFrame back to the Shifts sheet.
    Assumes df contains 'base_shift_name' and 'session_type'.
    """
    for _, row in df.iterrows():
        # Prepare data for update_row, ensuring base_shift_name and session_type are present
        data_to_update = row.to_dict()
        # Remove the constructed 'shift_name' if it exists, as it's not a sheet column
        data_to_update.pop('shift_name', None)
        update_row("Shifts", row['shift_id'], data_to_update)
    return True

@st.cache_data
def get_assignments_df():
    """Reads the Assignments sheet and returns a DataFrame."""
    return read_data("Assignments")

def update_assignments_df(df):
    """Writes the Assignments DataFrame back to the Assignments sheet."""
    for _, row in df.iterrows():
        update_row("Assignments", row['assignment_id'], row.to_dict())
    return True

@st.cache_data
def get_annual_leave_df():
    """Reads the Annual Leave sheet and returns a DataFrame."""
    return read_data("Annual_Leave")

@st.cache_data
def get_specialties_df():
    """Reads the Specialties sheet and returns a DataFrame."""
    return read_data("Specialties")

def generate_uuid():
    """Generates a unique identifier."""
    return str(uuid.uuid4())

# Example usage (for testing purposes, not part of the main app logic)
# if __name__ == "__main__":
#     # This part would typically be run in a separate test script or interactively
#     # For now, it's a placeholder to show how the functions might be used.
#     print("This is a test of google_sheets_manager.py")
#     print("Please ensure you have config.toml and Google Sheet set up.")

#     # Example: Read Users sheet
#     users_df = get_users_df()
#     if not users_df.empty:
#         print("Users DataFrame:")
#         print(users_df)
#     else:
#         print("Users sheet is empty or could not be read.")

#     # Example: Create a dummy user and append (only if sheet is empty for testing)
#     # if users_df.empty:
#     #     new_user = {
#     #         "user_id": generate_uuid(),
#     #         "name": "Test User",
#     #         "email": "test@example.com",
#     #         "start_date": "2024-01-01",
#     #         "annual_leave_total_days": 25,
#     #         "annual_leave_taken_days": 0,
#     #         "role": "GP",
#     #         "sessions_per_day_limit": 2,
#     #         "days_per_week_limit": 5,
#     #         "preferred_day_off": "None",
#     #         "availability": "{}"
#     #     }
#     #     # Note: append_row expects a list of values in the correct order
#     #     # You'd need to ensure the order matches your sheet columns
#     #     # For now, this is commented out to prevent accidental writes
#     #     # append_row("Users", list(new_user.values()))
#     #     print("Dummy user creation logic commented out.")
