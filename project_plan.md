# Project Plan: GP Surgery Shift Scheduling Streamlit App

This document outlines the plan for developing a Streamlit application to assist with scheduling shifts in a GP surgery, utilizing Google Sheets as the backend database.

## 1. Google Sheet Database Design (Sheet Name: "Orbitra")

The "Orbitra" Google Sheet will serve as the primary data store, organized into three distinct sheets. Each sheet will include a unique identifier column to ensure data integrity and facilitate referencing.

*   **Sheet 1: `Users` (for GP Surgery Staff)**
    *   **`user_id` (Unique Identifier):** A UUID (Universally Unique Identifier) for each staff member, automatically generated upon user creation.
    *   **`name`:** Full name of the staff member.
    *   **`email`:** Staff member's email address.
    *   **`start_date`:** Date when the staff member started.
    *   **`annual_leave_total_days`:** Total annual leave days allocated per year.
    *   **`annual_leave_taken_days`:** Annual leave days already taken this year.
    *   **`role`:** e.g., "GP", "Nurse", "Receptionist".
    *   **`sessions_per_day_limit`:** Maximum number of sessions a staff member can work per day.
    *   **`days_per_week_limit`:** Maximum number of days a staff member can work per week.
    *   **`preferred_day_off`:** A new column to specify a staff member's preferred day off (e.g., "Monday", "Tuesday", "None").
    *   **`availability`:** A flexible field to store recurring availability patterns (e.g., "Mon-Fri, 9-5"). This could be a JSON string or a reference to another sheet for more complex patterns.

*   **Sheet 2: `Shifts` (for Defined Shifts)**
    *   **`shift_id` (Unique Identifier):** A UUID for each defined shift type.
    *   **`shift_name`:** Descriptive name for the shift (e.g., "AM Clinic", "PM Clinic", "AM Admin").
    *   **`start_time`:** Fixed start times for shifts:
        *   **AM Clinic/Admin:** 08:00
        *   **PM Clinic:** 14:20 (assuming a break between AM and PM shifts)
    *   **`end_time`:** Fixed end times for shifts:
        *   **AM Clinic/Admin:** 12:10 (4 hours 10 minutes duration)
        *   **PM Clinic:** 18:30 (4 hours 10 minutes duration)
    *   **`required_role`:** The specific role required for this shift (e.g., "GP", "Nurse").
    *   **`capacity`:** The number of staff members required for this shift.
    *   **`is_admin_slot`:** A Boolean flag (TRUE/FALSE) to specifically identify administrative slots.

*   **Sheet 3: `Assignments` (for Scheduled Shifts and Annual Leave)**
    *   **`assignment_id` (Unique Identifier):** A UUID for each individual assignment record.
    *   **`date`:** The specific date of the assignment.
    *   **`shift_id`:** A reference (foreign key) to the `shift_id` from the `Shifts` sheet (if it's a work shift).
    *   **`user_id`:** A reference (foreign key) to the `user_id` from the `Users` sheet.
    *   **`type`:** Categorization of the assignment (e.g., "Work", "Annual Leave", "Sick Leave", "Admin").
    *   **`status`:** The current status of the assignment (e.g., "Scheduled", "Confirmed", "Pending").

## 2. Streamlit Application Structure & Functionality

The application will be developed using Streamlit, leveraging its interactive widgets and Python capabilities to provide a user-friendly interface.

*   **Core Components:**
    *   **Google Sheet Integration Module (`google_sheets_manager.py`):** This dedicated Python module will handle all interactions with Google Sheets, including reading, writing, and updating data. It will utilize the `gspread` library and the provided `secret Tomall` (TOML) configuration for secure authentication and access.
    *   **Data Models:** Python classes or Pydantic models will be used to represent `User`, `Shift`, and `Assignment` data. This ensures type safety, improves code readability, and facilitates data manipulation.
    *   **Constraint Programming Module (`shift_solver.py`):** A specialized module to encapsulate the `ortools` CP-SAT model. This module will be responsible for defining variables, adding constraints dynamically, and solving the shift assignment problem.

*   **User Interface (Streamlit Pages/Sections):**
    *   **Dashboard/Overview:** A central dashboard displaying the current week's schedule, upcoming annual leave, and key statistics related to shift assignments.
    *   **User Management:**
        *   An interface to display, add, edit, and delete staff members from the `Users` sheet.
        *   **CSV Upload:** A feature to allow bulk-adding or updating user data by uploading a CSV file.
        *   **Multi-select for Problem Assignment:** A `st.multiselect` widget to enable selecting a subset of users for specific tasks or to view their individual schedules.
        *   **New:** Dedicated input fields for `preferred_day_off` for each user.
    *   **Shift Definition:**
        *   An intuitive interface to define and manage different `Shifts`, including the newly specified "AM Admin" slot.
    *   **Shift Scheduling & Assignment:**
        *   **Date Selector:** Functionality to select the week or month for which shifts are to be scheduled.
        *   **Shift Slot Display:** A visual representation of available shift slots that need to be filled.
        *   **Assignment Interface:** Tools for assigning users to shifts, potentially including drag-and-drop or selection-based methods.
        *   **Annual Leave Management:** A dedicated section to input and track annual leave for staff, which will update `annual_leave_taken_days` in the `Users` sheet and create "Annual Leave" entries in the `Assignments` sheet.
    *   **Constraint Management (Enhanced):**
        *   **UI for Common Constraints:**
            *   Input fields for `sessions_per_day_limit` and `days_per_week_limit`.
            *   Dedicated input for `preferred_day_off` for each staff member.
            *   **New:** A user interface to define the number of "AM Admin" slots required per day and specify which roles are eligible for these slots.
            *   The fixed working hours (08:00-18:30) and precise shift durations (4h 10m for AM/PM) will be hardcoded into the `Shifts` definitions within the application logic.
        *   **Dynamic Constraint Builder (User-Friendly):**
            *   A user-friendly interface will be implemented where users can select from a predefined list of common constraint types (e.g., "Staff A cannot work with Staff B on the same shift", "Staff C must work at least X AM shifts per week", "Staff D cannot work more than Y consecutive shifts").
            *   For each selected constraint type, the UI will present relevant input fields (e.g., staff names, shift types, numerical values).
            *   This UI will dynamically generate the corresponding `ortools` CP-SAT constraints and add them to the model, providing a safer and more accessible way for non-developers to define constraints.
        *   **Advanced Custom Code Cell (for Developers):**
            *   For highly specific or complex constraints not covered by the dynamic builder, a dedicated "code cell" (Streamlit `st.text_area`) will be provided.
            *   Users with Python knowledge can write functions that receive the `cp_model` instance and relevant variables, allowing them to directly add `ortools` constraints.
            *   **Security Note:** This feature will require clear warnings about the risks of executing arbitrary code. Basic validation and error handling will be implemented, but users will be responsible for the code they input.
    *   **Algorithm Selection:** A sidebar element will allow users to select the shift allocation algorithm (starting with the `ortools` CP-SAT model).

## 3. Shift Assignment Algorithm & Visualization

*   **Base Algorithm:** The `ortools` CP-SAT model, as demonstrated in your example, will be the core of the shift assignment logic. It will be extended to incorporate all the defined constraints, including:
    *   Maximum sessions per week/day.
    *   Preferred day off (which can be implemented as a soft constraint to optimize for, or a hard constraint if strictly required).
    *   Specific allocation of "AM Admin" slots.
    *   Constraints generated by the dynamic constraint builder.
    *   Constraints provided through the advanced custom code cell.
*   **Visualization:** While `ortools` itself does not have built-in visualization capabilities, the results of the shift assignment will be clearly visualized within the Streamlit application. We will use Streamlit's native data display features along with popular Python visualization libraries such as `pandas`, `matplotlib`, or `plotly` to create engaging and informative displays. This could include:
    *   Calendar-like views showing which staff member is assigned to which shift on each day.
    *   Individual staff schedules.
    *   Summary statistics (e.g., total hours worked per staff, number of preferred days off met, constraint violations).

This comprehensive plan addresses all the requirements and clarifications provided, laying out a clear roadmap for the development of the GP surgery shift scheduling Streamlit application.
