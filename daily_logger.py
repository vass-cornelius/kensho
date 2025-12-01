import datetime
from pathlib import Path
import re
import argparse
import sys
import os
import calendar

from UniversalAtomicSolver.atomic_solver import AtomicSolver

# --- Configuration for Sections (for daily logs) ---
DAILY_SECTION_ORDER = [
    "What I did", "What's next", "What broke or got weird",
    "Productivity Score", "Quick Insights"
]
DAILY_SECTION_HEADERS = {
    "What I did": "## What I did", "What's next": "## What's next",
    "What broke or got weird": "## What broke or got weird",
    "Productivity Score": "## Productivity Score", "Quick Insights": "## Quick Insights"
}

# --- General Helper Functions ---
def get_bullet_points(prompt_message: str) -> list[str]:
    print(f"\n{prompt_message} (enter an empty line to finish):")
    items = []
    while True:
        item = input("- ").strip()
        if not item: break
        items.append(item)
    return items

def get_multiline_input(prompt_message: str) -> str:
    print(f"\n{prompt_message} (type 'END' on its own line to finish):")
    lines = []
    while True:
        line = sys.stdin.readline()
        if line.strip().upper() == 'END': break
        lines.append(line)
    return "".join(lines)

def get_log_directory() -> Path:
    default_log_dir_display = "~/daily_logs"
    default_log_dir_path = Path.home() / "daily_logs"
    prompt_message = (
        f"Enter the directory where log files are stored\n"
        f"or press Enter to use the default ({default_log_dir_display}): "
    )
    file_location_str = input(prompt_message)

    if not file_location_str:
        file_location = default_log_dir_path
        print(f"Using default directory: {file_location}")
    else:
        file_location = Path(file_location_str).expanduser()
        print(f"Using specified directory: {file_location}")

    try:
        file_location.mkdir(parents=True, exist_ok=True)
        return file_location
    except OSError as e:
        print(f"\n❌ Error: Could not create directory {file_location}. Reason: {e}")
        sys.exit(1)

# --- MONTHLY SUMMARY FUNCTIONS (UPDATED) ---

def run_monthly_summary(month_arg=None, logseq=False):
    """Handles the monthly summary workflow using the Gemini API."""
    print("\n--- 🧠 Monthly Summary & Insights Generation ---")

    log_dir = get_log_directory()

    # --- UPDATED: Determine the target month and year ---
    today = datetime.date.today()
    target_year = today.year
    target_month = None

    if month_arg is True: # User ran --monthly-summary with no number
        # Default to the previous full month
        first_day_of_current_month = today.replace(day=1)
        last_day_of_previous_month = first_day_of_current_month - datetime.timedelta(days=1)
        target_year = last_day_of_previous_month.year
        target_month = last_day_of_previous_month.month
    elif isinstance(month_arg, int): # User ran --monthly-summary <number>
        if not 1 <= month_arg <= 12:
            print("❌ Error: Invalid month number. Please provide a number between 1 and 12.")
            return
        target_month = month_arg
        # The year is assumed to be the current year
    else: # Should not be reached with the current argparse setup
        print("❌ Internal error with summary argument.")
        return

    month_name = calendar.month_name[target_month]
    print(f"\nAggregating logs for {month_name} {target_year}...")
    # --- END OF UPDATED LOGIC ---

    aggregated_content = []

    _, num_days_in_month = calendar.monthrange(target_year, target_month)
    weeks_in_month = set()
    for day_num in range(1, num_days_in_month + 1):
        d = datetime.date(target_year, target_month, day_num)
        _, week, _ = d.isocalendar()
        weeks_in_month.add(week)

    if logseq:
        """
        if we want to collect all files from a logseq folder, we need to follow its structure:
        - log_dir/journal/* contains all the daily logs (YYYY_MM_DD.md)
        - log_dir/pages/* contains the weekly files (YYYY___WXX (dd.mm. - dd.mm.).md)
        """
        journal_dir = log_dir / "journals"
        for file_path in journal_dir.iterdir():
            if file_path.suffix == ".md":
                if file_path.name.startswith(f"{target_year}_{target_month:02d}"):
                    aggregated_content.append(f"\n--- Content from {file_path.name} ---\n{file_path.read_text(encoding='utf-8')}")

        weekly_dir = log_dir / "pages"
        for file_path in weekly_dir.iterdir():
            if file_path.suffix == ".md":
                match = re.fullmatch(rf"(\d{{4}})___W(\d{{2}})_(\d{{2}}\.\d{{2}})\.md", file_path.name)
                if match:
                    log_year, log_week = int(match.group(1)), int(match.group(2))
                    if log_year == target_year and log_week in weeks_in_month:
                        aggregated_content.append(
                            f"\n--- Content from {file_path.name} ---\n{file_path.read_text(encoding='utf-8')}")

    else:
        for file_path in log_dir.iterdir():
            if file_path.suffix == ".md":
                if file_path.name.startswith(f"daily-log-{target_year}-{target_month:02d}"):
                    aggregated_content.append(f"\n--- Content from {file_path.name} ---\n{file_path.read_text(encoding='utf-8')}")
                match = re.fullmatch(rf"(\d{{4}})-W(\d{{2}})\.md", file_path.name)
                if match:
                    log_year, log_week = int(match.group(1)), int(match.group(2))
                    if log_year == target_year and log_week in weeks_in_month:
                        aggregated_content.append(f"\n--- Content from {file_path.name} ---\n{file_path.read_text(encoding='utf-8')}")

    if not aggregated_content:
        print(f"\nNo log files found for {month_name} {target_year}. Nothing to summarize.")
        return

    full_log_text = "\n".join(aggregated_content)
    print(f"Found {len(aggregated_content)} log entries. Total length: {len(full_log_text)} characters.")

    goal = f"""
    As a helpful productivity coach, your task is to perform a deep and insightful analysis of the personal logs to help me understand my work patterns, celebrate successes, identify challenges, and improve in the future.
    Generate a report with the exact following structure and headers (For each section, provide thoughtful, data-driven analysis based *only* on the personal logs provided).    
    """

    # full_prompt = prompt + "\n" + full_log_text
    context = (f"""
    I am providing you with a collection of my personal logs from a specific period, which includes both daily and weekly entries. 
    
    First, understand the structure of my logs:

    * **Daily Logs** contain:
        * `What I did`: A list of completed tasks.
        * `What's next`: Planned future tasks.
        * `What broke or got weird`: Challenges, bugs, and blockers.
        * `Productivity Score`: A self-rated score from 1-5 for the day. A history may be present, where old scores are struck through (e.g., `- ~~3/5~~`, `- 4/5`). Please use the final, unstruck score for any daily analysis.
    * **Weekly Logs** contain:
        * **Start of Week (SOW):** `My Goals for the Week`, `Next Steps`, and `Other Tasks`.
        * **End of Week (EOW):** A review with `What went well?`, `What are you happy about?`, `What made you laugh?`, and `Progress observed`.
        
    <Report_Template>
    # Productivity & Progress Analysis for <month_name>/<year>

    ## 🎯 Executive Summary
    Provide a 2-3 sentence high-level summary of the period. What was the main story of this month/week? Was it a period of high achievement, overcoming challenges, or steady progress?

    ## ✅ Accomplishments vs. Goals
    Analyze the alignment between my stated weekly goals and my daily actions.

    * **Goals Achieved:** List the weekly goals that were clearly met, citing specific entries from "What I did" or "What went well" as evidence.
    * **Goals Partially Achieved or Missed:** Identify goals that were not fully completed or mentioned. Speculate on why, based on the "What broke" sections or a lack of related daily tasks.
    * **Unplanned Accomplishments:** Highlight significant achievements from the "What I did" logs that were not part of the stated weekly goals.

    ## 📈 Productivity Analysis
    Perform a quantitative and qualitative analysis of my productivity scores.

    * **Score Overview:** What was my average productivity score? What was the range of scores (highest and lowest)?
    * **Trend Analysis:** Was there a noticeable trend in productivity (e.g., increasing over the month, higher at the start of the week vs. the end)?
    * **Correlation:** Correlate the highest-rated productivity days with the activities performed on those days. What kind of work leads to a feeling of high productivity? Conversely, what activities or events from the "What broke" section correspond with the lowest-rated days?

    ## 🚧 Recurring Challenges & Blockers
    Synthesize all entries from "What broke or got weird" across the daily logs.

    * **Identify Themes:** Group similar problems together to identify recurring patterns. Are there repeated technical issues, specific types of interruptions, or common sources of frustration?
    * **Impact Assessment:** Briefly describe the likely impact of these recurring issues on my goals and productivity.

    ## 😊 Sources of Success & Happiness
    Analyze the qualitative data from the End of Week reviews to understand the drivers of success and well-being.

    * **What Drives Success:** What are the common themes in the "What went well" and "Progress observed" sections?
    * **Sources of Joy:** What patterns do you see in the "What are you happy about?" and "What made you laugh?" sections? This helps identify what makes the work sustainable and enjoyable.

    ## 🌱 Actionable Recommendations
    Based on your entire analysis, provide a short list of concrete, actionable recommendations for the next period.

    1.  **To Capitalize on Strengths:** Suggest one action to double down on what's already working well.
    2.  **To Address Challenges:** Propose one specific strategy to mitigate the most significant recurring blocker you identified.
    3.  **To Improve Alignment:** Recommend one way I can better align my daily tasks with my weekly goals.
    4.  **A Question for Reflection:** Pose one insightful question for me to think about during my next planning session.
    </Report_Template>
    """) + "\n<personal_logs>" + full_log_text + "\n</personal_logs>"

    print("\nSending data to Gemini for analysis... This may take a moment.")
    solver = AtomicSolver(api_key=os.getenv("gemini_api_key"))

    try:
        # model = genai.GenerativeModel(api_model)
        # response = model.generate_content(full_prompt)
        # summary_text = response.text
        summary_text = solver.run(goal=goal, context=context)
    except Exception as e:
        print(f"\n❌ An error occurred with the Gemini API: {e}")
        return

    # Summary file name is in the format: <year>/Progress/<monthname>.md
    # Example: 2025/Progress/November.md
    month_name = target_month.strftime("%B")
    summary_file_name = f"{target_year}___Progress___{month_name}.md"

    if logseq:
        summary_file_name = f"{target_year}___Progress___{month_name}.md"
        summary_file_path = log_dir / "pages" / summary_file_name
    else:
        summary_file_path = log_dir / summary_file_name

    try:
        summary_file_path.write_text(summary_text, encoding="utf-8")
        print(f"\n✅ Successfully generated and saved monthly summary to: {summary_file_path}")
    except IOError as e:
        print(f"\n❌ Error: Could not write summary file. Reason: {e}")


# --- WEEKLY & DAILY LOG FUNCTIONS (Unchanged) ---
# ... (all functions from `run_sow_log` to `write_daily_log_file` are here, unchanged) ...
def run_sow_log(logseq=False):
    print("\n--- 🚀 Start of Week Planning ---")
    log_dir = get_log_directory()
    today = datetime.date.today()
    year, week, _ = today.isocalendar()
    start_of_week = today - datetime.timedelta(days=today.weekday())
    end_of_week = start_of_week + datetime.timedelta(days=6)

    if logseq:
        file_name = f"{year}___W{week:02d}___({start_of_week.strftime('%d.%m.')} - {end_of_week.strftime('%d.%m.')}).md"
        file_path = log_dir / "pages" / file_name
    else:
        file_name = f"{year}-W{week:02d}.md"
        file_path = log_dir / file_name

    print(f"\nThis will create/overwrite the weekly log at: {file_path}")
    goals = get_bullet_points("Set yourself one or two or three goals for the week.")
    next_steps = get_bullet_points("What are the next steps you need to take to achieve your goals?")
    other_tasks = get_bullet_points("What other tasks spring to mind?")
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            if logseq:
                f.write(f"exclude-from-graph-view:: true\n\n")
                f.write(f"- # Weekly Log for {year}, Week {week}\n")
                f.write(f"_{start_of_week.strftime('%B %d')} - {end_of_week.strftime('%B %d, %Y')}_\n\n")
                f.write("- ## My Goals for the Week\n"); [f.write(f"- {item}\n") for item in goals] if goals else f.write("- N/A\n"); f.write("\n")
                f.write("- ## Next Steps\n"); [f.write(f"- {item}\n") for item in next_steps] if next_steps else f.write("- N/A\n"); f.write("\n")
                f.write("- ## Other Tasks\n"); [f.write(f"- {item}\n") for item in other_tasks] if other_tasks else f.write("- N/A\n"); f.write("\n")
            else:
                f.write(f"# Weekly Log for {year}, Week {week}\n")
                f.write(f"_{start_of_week.strftime('%B %d')} - {end_of_week.strftime('%B %d, %Y')}_\n\n")
                f.write("## My Goals for the Week\n"); [f.write(f"- {item}\n") for item in goals] if goals else f.write("- N/A\n"); f.write("\n")
                f.write("## Next Steps\n"); [f.write(f"- {item}\n") for item in next_steps] if next_steps else f.write("- N/A\n"); f.write("\n")
                f.write("## Other Tasks\n"); [f.write(f"- {item}\n") for item in other_tasks] if other_tasks else f.write("- N/A\n"); f.write("\n")
        print(f"\n✅ Successfully saved Start of Week plan to: {file_path}")
    except IOError as e: print(f"\n❌ Error: Could not write to file {file_path}. Reason: {e}")

def run_eow_log(logseq=False):
    print("\n--- ⭐ End of Week Review ---")
    log_dir = get_log_directory()
    today = datetime.date.today()
    year, week, _ = today.isocalendar()
    
    if logseq:
        start_of_week = today - datetime.timedelta(days=today.weekday())
        end_of_week = start_of_week + datetime.timedelta(days=6)
        file_name = f"{year}___W{week:02d}___({start_of_week.strftime('%d.%m.')} - {end_of_week.strftime('%d.%m.')}).md"
        file_path = log_dir / "pages" / file_name
    else:
        file_name = f"{year}-W{week:02d}.md"
        file_path = log_dir / file_name
    
    if not file_path.exists():
        print(f"\n❌ Error: Weekly log '{file_path}' not found. Please run --sow first.")
        return
    
    print(f"\nThis will append a review to the weekly log at: {file_path}")
    went_well = get_multiline_input("Based on your logs: What went well?")
    happy_about = get_multiline_input("What are you happy about?")
    made_laugh = get_multiline_input("What made you laugh?")
    progress = get_multiline_input("Please describe any progress that you have observed.")
    try:
        with open(file_path, "a", encoding="utf-8") as f:
            if logseq:
                f.write("\n- ---\n")
                f.write("- ## End of Week Review\n")
                f.write(f" - ### What went well?\n{went_well if went_well.strip() else 'N/A'}\n\n")
                f.write(f" - ### What are you happy about?\n{happy_about if happy_about.strip() else 'N/A'}\n\n")
                f.write(f" - ### What made you laugh?\n{made_laugh if made_laugh.strip() else 'N/A'}\n\n")
                f.write(f" - ### Please describe any progress that you have observed.\n{progress if progress.strip() else 'N/A'}\n\n")
            else:
                f.write("\n---\n\n## End of Week Review\n\n")
                f.write(f"### What went well?\n{went_well if went_well.strip() else 'N/A'}\n\n")
                f.write(f"### What are you happy about?\n{happy_about if happy_about.strip() else 'N/A'}\n\n")
                f.write(f"### What made you laugh?\n{made_laugh if made_laugh.strip() else 'N/A'}\n\n")
                f.write(f"### Please describe any progress that you have observed.\n{progress if progress.strip() else 'N/A'}\n\n")
        print(f"\n✅ Successfully appended End of Week review to: {file_path}")
    except IOError as e: print(f"\n❌ Error: Could not write to file {file_path}. Reason: {e}")

def get_daily_productivity_score() -> int:
    while True:
        try:
            score = int(input("\nProductivity score (1-5): "))
            if 1 <= score <= 5: return score
            else: print("Invalid score. Please enter a number between 1 and 5.")
        except ValueError: print("Invalid input. Please enter a number.")

def collect_all_daily_inputs() -> dict:
    new_inputs = {}
    print("\nPlease provide your new entries for today's log:")
    new_inputs["What I did"] = get_bullet_points("What I did (new entries):")
    new_inputs["What's next"] = get_bullet_points("What's next (new entries):")
    new_inputs["What broke or got weird"] = get_bullet_points("What broke or got weird (new entries):")
    new_inputs["Productivity Score"] = get_daily_productivity_score()
    new_quick_insights = []
    add_insights_prompt = input("\nDo you want to add any quick insights? (yes/no, default: no): ").strip().lower()
    if add_insights_prompt.startswith('y'):
        new_quick_insights = get_bullet_points("Quick insights (new entries):")
    new_inputs["Quick Insights"] = new_quick_insights
    return new_inputs

def parse_existing_daily_file(file_path: Path) -> dict:
    parsed_content = {key: [] for key in DAILY_SECTION_ORDER}
    if not file_path.exists(): return parsed_content
    with open(file_path, "r", encoding="utf-8") as f: lines = f.readlines()
    current_section_key = None
    for line in lines:
        stripped_line = line.strip()
        matched_header = False
        for key_from_config in DAILY_SECTION_ORDER:
            if stripped_line == DAILY_SECTION_HEADERS[key_from_config]:
                current_section_key = key_from_config
                matched_header = True
                break
        if matched_header: continue
        if current_section_key and stripped_line and stripped_line.startswith("- "):
            parsed_content[current_section_key].append(stripped_line)
    return parsed_content

def generate_daily_output_lines(existing_content: dict, new_inputs: dict, today_date_str: str) -> list[str]:
    output_lines = [f"# Daily Log - {today_date_str}\n\n"]
    for section_key in DAILY_SECTION_ORDER:
        section_header = DAILY_SECTION_HEADERS[section_key]
        current_section_content_lines = []
        if section_key == "Productivity Score":
            processed_score_history = []
            for old_score_line in existing_content.get(section_key, []):
                match = re.fullmatch(r"- (\d/5)", old_score_line)
                if match: processed_score_history.append(f"- ~~{match.group(1)}~~")
                elif old_score_line != "- N/A": processed_score_history.append(old_score_line)
            processed_score_history.append(f"- {new_inputs['Productivity Score']}/5")
            current_section_content_lines.extend(processed_score_history)
        else:
            combined_items = existing_content.get(section_key, [])[:]
            for new_item_text in new_inputs.get(section_key, []): combined_items.append(f"- {new_item_text}")
            current_section_content_lines.extend(combined_items)
        if section_key == "Quick Insights" and not current_section_content_lines: continue
        output_lines.append(f"{section_header}\n")
        if current_section_content_lines:
            for item_line in current_section_content_lines: output_lines.append(f"{item_line}\n")
        else: output_lines.append("- N/A\n")
        output_lines.append("\n")
    return output_lines

def write_daily_log_file(file_path: Path, output_lines: list[str]):
    try:
        with open(file_path, "w", encoding="utf-8") as f: f.writelines(output_lines)
        print(f"\n✅ Successfully saved daily log to: {file_path}")
    except IOError as e: print(f"\n❌ Error: Could not write to file {file_path}. Reason: {e}")

def run_daily_log(logseq=False):
    if logseq:
        # let user know he should be using logseqs' daily log feature (journal) instead
        print("\n❌ Error: Daily log feature is not supported for Logseq. Please use Logseq's journal feature instead.")
        return
    print("📝 Daily Log Script")
    print("----------------------------------------------------------")
    log_dir = get_log_directory(logseq=logseq)
    today_date_str = datetime.date.today().strftime("%Y-%m-%d")
    file_name = f"daily-log-{today_date_str}.md"
    file_path = log_dir / file_name
    print(f"\nDaily log file will be managed at: {file_path}")
    new_user_inputs = collect_all_daily_inputs()
    existing_log_content = parse_existing_daily_file(file_path)
    if file_path.exists(): print(f"\nFound existing log for today. Merging entries.")
    else: print(f"\nCreating new log for today.")
    final_output_lines = generate_daily_output_lines(existing_log_content, new_user_inputs, today_date_str)
    write_daily_log_file(file_path, final_output_lines)

# --- MAIN (UPDATED) ---
def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="A script for daily, weekly, and monthly logging and analysis.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--sow", action="store_true", help="Run the Start of Week (SOW) questions.")
    group.add_argument("--eow", action="store_true", help="Run the End of Week (EOW) questions.")
    group.add_argument(
        "--monthly-summary",
        nargs='?', # Makes the value optional.
        const=True, # Value if flag is present with no number.
        default=None, # Value if flag is not present.
        type=int, # The value will be an integer.
        metavar='MONTH', # A name for the value in help text.
        help="Generate a summary for a specific month of the current year (e.g., 5 for May).\nIf no month number is given, summarizes the previous full month."
    )
    parser.add_argument(
        "--logseq",
        action="store_true",
        help="Use a logseq folder for aggregation."
    )

    args = parser.parse_args()

    if args.sow:
        run_sow_log(logseq=args.logseq)
    elif args.eow:
        run_eow_log(logseq=args.logseq)
    elif args.monthly_summary is not None:
        run_monthly_summary(month=args.monthly_summary, logseq=args.logseq)
    else:
        run_daily_log(logseq=args.logseq)

    print("\nScript finished.")

if __name__ == "__main__":
    main()
