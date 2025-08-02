from ortools.sat.python import cp_model
import pandas as pd
import uuid

def solve_shift_scheduling(users_df, shifts_df, start_date, num_days=7, daily_staffing_req=None):
    """
    Solves the shift scheduling problem using CP-SAT.

    Args:
        users_df (pd.DataFrame): DataFrame containing user data.
        shifts_df (pd.DataFrame): DataFrame containing shift definitions.
        start_date (datetime.date): The starting date for the scheduling period.
        num_days (int): The number of days to schedule.

    Returns:
        pd.DataFrame: A DataFrame of assigned shifts, or None if no feasible solution.
    """
    model = cp_model.CpModel()

    # --- Data Preparation ---
    staff_names = users_df['name'].tolist()
    staff_ids = users_df['user_id'].tolist()
    staff_roles = users_df.set_index('user_id')['role'].to_dict()
    staff_sessions_per_day_limit = users_df.set_index('user_id')['sessions_per_day_limit'].to_dict()
    staff_preferred_day_off = users_df.set_index('user_id')['preferred_day_off'].to_dict()

    shift_ids = shifts_df['shift_id'].tolist()
    shift_required_roles = shifts_df.set_index('shift_id')['required_role'].to_dict()
    shift_capacities = shifts_df.set_index('shift_id')['capacity'].to_dict()
    shift_required_days = shifts_df.set_index('shift_id')['required_days'].to_dict()
    shift_base_names = shifts_df.set_index('shift_id')['base_shift_name'].to_dict()
    shift_session_types = shifts_df.set_index('shift_id')['session_type'].to_dict()

    # Create a list of dates for the scheduling period
    dates = [start_date + pd.Timedelta(days=i) for i in range(num_days)]
    days_of_week = [date.strftime('%A') for date in dates] # e.g., "Monday"

    # --- Variables ---
    # assigned[(staff_id, date, shift_id)] = 1 if staff is assigned to shift on date
    assigned = {}
    for s_id in staff_ids:
        for date in dates:
            for sh_id in shift_ids:
                assigned[(s_id, date, sh_id)] = model.NewBoolVar(f'assigned_{s_id}_{date.strftime("%Y%m%d")}_{sh_id}')

    # --- Constraints ---

    # 1. Each shift must have its required capacity filled on its required days
    for i, date in enumerate(dates):
        day_of_week = days_of_week[i]
        for sh_id in shift_ids:
            required_days = shift_required_days[sh_id]
            # If the shift is required on this day, enforce capacity
            if isinstance(required_days, str) and day_of_week in required_days:
                model.Add(sum(assigned[(s_id, date, sh_id)] for s_id in staff_ids) == shift_capacities[sh_id])
            # If the shift is NOT required on this day, ensure no one is assigned
            else:
                model.Add(sum(assigned[(s_id, date, sh_id)] for s_id in staff_ids) == 0)

    # 2. A staff member can only be assigned to one shift at a time (assuming shifts don't overlap for simplicity)
    # This constraint needs to be more sophisticated if shifts can overlap.
    # For now, assuming AM/PM are distinct and non-overlapping.
    # If a staff member is assigned to an AM shift, they cannot be assigned to a PM shift on the same day.
    # This is implicitly handled by the "sessions per day" limit if each shift counts as a session.
    # Let's refine this: a staff member can only work one AM and one PM shift per day.
    # This is better handled by limiting total sessions per day.

    # 3. Max sessions per staff per day
    for s_id in staff_ids:
        for date in dates:
            model.Add(sum(assigned[(s_id, date, sh_id)] for sh_id in shift_ids) <= staff_sessions_per_day_limit[s_id])

    # 4. Max days per staff per week
    # This constraint is removed as we are now specifying preferred days off.

    # 5. Staff role must match required role for the shift
    for s_id in staff_ids:
        for date in dates:
            for sh_id in shift_ids:
                if shift_required_roles[sh_id] != "Any" and staff_roles[s_id] != shift_required_roles[sh_id]:
                    model.Add(assigned[(s_id, date, sh_id)] == 0) # Cannot assign if roles don't match

    # 6. Preferred day off (soft constraint for now, can be made hard if needed)
    # This can be implemented by penalizing assignments on preferred days off.
    # For a hard constraint:
    for s_id in staff_ids:
        preferred_day = staff_preferred_day_off[s_id]
        if preferred_day != "None":
            for i, date in enumerate(dates):
                if days_of_week[i] == preferred_day:
                    # If it's their preferred day off, they cannot be assigned
                    model.Add(sum(assigned[(s_id, date, sh_id)] for sh_id in shift_ids) == 0)

    # 7. Daily staffing requirements
    if daily_staffing_req:
        for i, date in enumerate(dates):
            day_of_week = days_of_week[i]
            for role, requirements in daily_staffing_req.items():
                min_staff = requirements.get(day_of_week, 0)
                if min_staff > 0:
                    staff_in_role = [s_id for s_id, r in staff_roles.items() if r == role]
                    if staff_in_role:
                        model.Add(sum(assigned[(s_id, date, sh_id)] for s_id in staff_in_role for sh_id in shift_ids) >= min_staff)

    # 7. Soft Constraint: Prefer AM/PM shifts of the same base_shift_name for users working 2 sessions
    violations = []
    # Group shifts by base_shift_name to find potential AM/PM pairs
    shifts_by_base_name = shifts_df.groupby('base_shift_name')['shift_id'].apply(list).to_dict()

    for s_id in staff_ids:
        # Apply this rule only to users who can work 2 sessions a day
        if staff_sessions_per_day_limit.get(s_id, 1) >= 2:
            for date in dates:
                # Find all pairs of shifts with different base names
                for i, sh_id1 in enumerate(shift_ids):
                    for j, sh_id2 in enumerate(shift_ids):
                        if i < j and shift_base_names[sh_id1] != shift_base_names[sh_id2]:
                            # This variable is true if the user is assigned to this specific pair of shifts
                            are_both_assigned = model.NewBoolVar(f'are_both_assigned_{s_id}_{date.strftime("%Y%m%d")}_{sh_id1}_{sh_id2}')
                            model.AddBoolAnd([assigned[(s_id, date, sh_id1)], assigned[(s_id, date, sh_id2)]]).OnlyEnforceIf(are_both_assigned)
                            model.Add(sum([assigned[(s_id, date, sh_id1)], assigned[(s_id, date, sh_id2)]]) < 2).OnlyEnforceIf(are_both_assigned.Not())

                            # This is a violation
                            violations.append(are_both_assigned)

    # Minimize the total number of violations
    model.Minimize(sum(violations))

    # --- Solve Model ---
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    # --- Process Results ---
    assigned_shifts_list = []
    if status == cp_model.FEASIBLE or status == cp_model.OPTIMAL:
        for s_id in staff_ids:
            for date in dates:
                for sh_id in shift_ids:
                    if solver.Value(assigned[(s_id, date, sh_id)]) == 1:
                        assigned_shifts_list.append({
                            "assignment_id": str(uuid.uuid4()),
                            "date": date.strftime("%Y-%m-%d"),
                            "shift_id": sh_id,
                            "user_id": s_id,
                            "type": "Work", # Assuming all are work for now
                            "status": "Scheduled"
                        })
        return pd.DataFrame(assigned_shifts_list), status, "Feasible solution found."
    else:
        # Provide a reason for infeasibility
        if status == cp_model.INFEASIBLE:
            # You can add more sophisticated analysis here to pinpoint the exact conflict.
            # For now, we provide a general message and check for common issues.
            # For example, check if total capacity required exceeds total staff available for any role.
            return None, status, "No feasible solution found. Check for conflicting constraints, such as staff availability vs. shift requirements, or too many preferred days off."
        else:
            return None, status, "Solver stopped for other reasons (e.g., time limit)."

# Example usage (for testing purposes)
if __name__ == "__main__":
    # Dummy DataFrames for testing
    sample_users_data = [
        {"user_id": "user1", "name": "Shuman", "email": "shuman@example.com", "start_date": "2023-01-01", "annual_leave_total_days": 25, "annual_leave_taken_days": 0, "role": "GP", "sessions_per_day_limit": 2, "days_per_week_limit": 5, "preferred_day_off": "Saturday", "availability": "{}"},
        {"user_id": "user2", "name": "Andrew", "email": "andrew@example.com", "start_date": "2023-01-01", "annual_leave_total_days": 25, "annual_leave_taken_days": 0, "role": "GP", "sessions_per_day_limit": 2, "days_per_week_limit": 5, "preferred_day_off": "Sunday", "availability": "{}"},
        {"user_id": "user3", "name": "Rhiannon", "email": "rhiannon@example.com", "start_date": "2023-01-01", "annual_leave_total_days": 25, "annual_leave_taken_days": 0, "role": "Nurse", "sessions_per_day_limit": 2, "days_per_week_limit": 5, "preferred_day_off": "None", "availability": "{}"},
        {"user_id": "user4", "name": "Jenny", "email": "jenny@example.com", "start_date": "2023-01-01", "annual_leave_total_days": 25, "annual_leave_taken_days": 0, "role": "Receptionist", "sessions_per_day_limit": 2, "days_per_week_limit": 5, "preferred_day_off": "Monday", "availability": "{}"},
    ]
    sample_users_df = pd.DataFrame(sample_users_data)

    sample_shifts_data = [
        {"shift_id": "shift1", "shift_name": "AM Clinic", "start_time": "08:00", "end_time": "12:10", "required_role": "GP", "capacity": 2, "is_admin_slot": False},
        {"shift_id": "shift2", "shift_name": "PM Clinic", "start_time": "14:20", "end_time": "18:30", "required_role": "GP", "capacity": 2, "is_admin_slot": False},
        {"shift_id": "shift3", "shift_name": "AM Admin", "start_time": "08:00", "end_time": "12:10", "required_role": "Any", "capacity": 1, "is_admin_slot": True},
    ]
    sample_shifts_df = pd.DataFrame(sample_shifts_data)

    import datetime
    start_date_test = datetime.date(2025, 8, 4) # Monday

    print("Attempting to solve shift scheduling...")
    assigned_df = solve_shift_scheduling(sample_users_df, sample_shifts_df, start_date_test, num_days=7)

    if assigned_df is not None:
        print("\nFeasible solution found:")
        print(assigned_df)

        # Basic visualization for testing
        print("\n--- Schedule Overview ---")
        for date in sorted(assigned_df['date'].unique()):
            print(f"\nDate: {date}")
            daily_assignments = assigned_df[assigned_df['date'] == date]
            for shift_id in sorted(daily_assignments['shift_id'].unique()):
                shift_name = sample_shifts_df[sample_shifts_df['shift_id'] == shift_id]['shift_name'].iloc[0]
                assigned_users = daily_assignments[daily_assignments['shift_id'] == shift_id]['user_id'].tolist()
                assigned_user_names = [sample_users_df[sample_users_df['user_id'] == uid]['name'].iloc[0] for uid in assigned_users]
                print(f"  {shift_name}: {', '.join(assigned_user_names)}")
    else:
        print("\nNo feasible solution found for the given constraints.")
