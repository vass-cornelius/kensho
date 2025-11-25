import os
import json # For parsing Gemini's JSON suggestions
import re   # For parsing user choice for picking suggestions
import textwrap # For dedenting multiline strings
from pathlib import Path # For handling home directory and paths
from datetime import datetime # For generating date-stamped filenames

try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.text import Text
    from rich.panel import Panel
    # from rich.style import Style # Style object is not strictly needed if using hex strings directly
except ImportError:
    print("The 'rich' library is not installed. This script now requires it.")
    print("Please install it by running: pip install rich")
    exit()

try:
    import google.generativeai as genai
except ImportError:
    print("The 'google-generativeai' library is not installed.")
    print("Please install it by running: pip install google-generativeai")
    exit()

# --- Rich Console Initialization ---
console = Console(width=120) # Adjust width as desired

# --- Hex Color Definitions ---
CLR_BRIGHT_MAGENTA = "#FF55FF"
CLR_MAGENTA = "#FF00FF"
CLR_SKY_BLUE = "#87CEEB"       # Standard SkyBlue
CLR_STEEL_BLUE = "#4682B4"     # Standard SteelBlue
CLR_DODGER_BLUE = "#1E90FF"    # Standard DodgerBlue
CLR_PLUM = "#DDA0DD"           # Standard Plum
CLR_ROYAL_BLUE = "#4169E1"     # Standard RoyalBlue
CLR_DEEP_SKY_BLUE = "#00BFFF"  # Standard DeepSkyBlue
CLR_YELLOW = "#FFFF00"
CLR_GOLD = "#FFD700"
CLR_GREEN = "#00FF00"
CLR_CHARTREUSE = "#7FFF00"
CLR_RED = "#FF0000"
CLR_BRIGHT_RED = "#FF4444"
CLR_CYAN = "#00FFFF"
CLR_DIM_WHITE = "#BBBBBB"
CLR_ORANGE = "#FFA500"

# --- Configuration ---
API_KEY = os.getenv("GEMINI_API_KEY")

# --- TEMPLATE_SECTIONS (Focus on "In Detail" and "Cost & Revenue") ---
TEMPLATE_SECTIONS = [
    {"id": "main_title", "title": "MOTION Document Title", "type": "main_title", # Essential, asked first
     "guidance": """Your proposal should always begin with a clear and concise 'Title'.
This title should be a succinct name for your initiative. It sets the stage and defines the overall focus.""",
     "gemini_base_prompt": "Brainstorm some impactful and descriptive titles for an initiative. It should convey [key benefit or outcome]. My initial idea for the initiative is: ",
     "ask_gemini": True},

    # "General Info" sections are omitted as per user request.

    # In Detail Category
    {"id": "summary", "title": "Summary", "category": "In Detail", "required": True,
     "description": "Required - Provide a short summary of the proposal, at most one or two short and sweet sentences.",
     "guidance": """Start with a concise 'Summary'. This is your 'elevator pitch' –
a very brief explanation of the core issue, opportunity, or idea your initiative addresses.""",
     "gemini_base_prompt": "Help me craft a 1-2 sentence summary that is impactful and captures the essence. My initiative is about: ",
     "ask_gemini": True},
    {"id": "goals_output", "title": "Goals expected output", "category": "In Detail", "required": True,
     "description": "Required\nWhat are the goals of this proposal?\n• What are the expected output of this proposal?",
     "guidance": """Clearly define the 'Goals' – what you aim to achieve.
Goals should be **SMART** (Specific, Measurable, Achievable, Relevant, Time-bound).
'Expected outputs' are the tangible results or deliverables.""",
     "gemini_base_prompt": "Help me define 3-5 clear, SMART goals and their key tangible outputs. My initiative's summary is: ",
     "ask_gemini": True},
    {"id": "non_goals", "title": "Non-Goals", "category": "In Detail",
     "description": "Describe any goals you wish to identify specifically as being out of scope for this proposal.",
     "guidance": """Explicitly state what is *out of scope* for your initiative.
This manages expectations and prevents 'scope creep'.""",
     "gemini_base_prompt": "What are common related areas that I should explicitly state as non-goals to avoid confusion? My initiative's goals are: ",
     "ask_gemini": True},
    {"id": "success_metrics", "title": "Success Metrics", "category": "In Detail",
     "description": "If the success of this work can be gauged by specific numerical metrics and associated goals then describe them here.",
     "guidance": """Specify how you'll objectively measure progress and success using quantifiable metrics (KPIs).
These should be numerical for objective tracking.""",
     "gemini_base_prompt": "For each of my goals, help me brainstorm specific, measurable success metrics (KPIs). How can I establish baselines and targets? My goals are: ",
     "ask_gemini": True},
    {"id": "motivation", "title": "Motivation", "category": "In Detail",
     "description": "Why should this work be done? What are its benefits? Who's asking for it? How does it compare to the competition, if any?",
     "guidance": """Explain *why* this initiative is necessary. What problem does it solve?
What are its benefits? Who is asking for it?
Consider using the **'5 Whys' technique** to delve deeper.
Also, briefly address how this initiative or its approach compares to existing internal methods, market alternatives, or competitors, if applicable. This helps establish its value or uniqueness.""",
     "gemini_base_prompt": "Help me articulate a strong motivation, potentially using the '5 Whys'. What are the key benefits? Who is asking for this? Also, how does this initiative compare to existing alternatives or competitors? My initiative is about: ",
     "ask_gemini": True},
    {"id": "description_detailed", "title": "Description", "category": "In Detail", "required": True,
     "description": "Required - More detail description of the initiative and detailed expected outcome",
     "guidance": """Elaborate on your proposed initiative. Explain the 'what' and 'how',
methodology, key activities/phases, and detailed expected outcomes.""",
     "gemini_base_prompt": "Help me elaborate on my initiative into a detailed description covering methodology, key activities, phases, and detailed outcomes. My summary and goals are: ",
     "ask_gemini": True},
    {"id": "alternatives", "title": "Alternatives", "category": "In Detail",
     "description": "Did you consider any alternative approaches or technologies? If so then please describe them here and explain why they were not chosen.",
     "guidance": """Document other approaches or technologies you considered.
For each, briefly explain it and why it was not chosen (e.g., pros/cons, feasibility).""",
     "gemini_base_prompt": "What are 2-3 plausible alternative approaches for [initiative X]? For each, help me articulate concise reasons for not choosing them.",
     "ask_gemini": True},
    {"id": "risks_assumptions", "title": "Risks and Assumptions", "category": "In Detail",
     "description": "Describe any risks or assumptions that must be considered along with this proposal. Could any plausible events derail this work, or even render it unnecessary? If you have mitigation plans for the known risks then please describe them.",
     "guidance": """Identify potential 'Risks' (what could go wrong) and 'Assumptions' (what you believe to be true for your plan).
For significant risks, consider Likelihood/Impact and outline Mitigation/Contingency plans.""",
     "gemini_base_prompt": "What are common risks and assumptions for an initiative like [user input]? For a key risk, help me think about its likelihood, impact, and mitigation strategies.",
     "ask_gemini": True},
    {"id": "dependencies", "title": "Dependencies", "category": "In Detail",
     "description": "Describe all dependencies this Initiative has on another one or components, products, or anything else.",
     "guidance": """Identify tasks, resources, or inputs from other teams/projects that your initiative relies on, or outputs others depend on.
This is crucial for planning and coordination.""",
     "gemini_base_prompt": "My initiative involves [components/teams]. What kind of dependencies should I consider and list? How can I best articulate them?",
     "ask_gemini": True},

    # Cost & Revenue Category
    {"id": "cost", "title": "Cost", "category": "Cost & Revenue",
     "description": "Expected costs in terms of time needed (high level estimation)",
     "guidance": """Provide a high-level estimation of costs, primarily in terms of time needed (e.g., person-days).
This helps assess feasibility.""",
     "gemini_base_prompt": "My initiative involves [tasks/components]. How can I create a high-level time estimation? What factors should I consider?",
     "ask_gemini": True},
    {"id": "revenue", "title": "Revenue", "category": "Cost & Revenue",
     "description": "Expected revenue in case of a Strategic MOTION.",
     "guidance": """Quantify the value your initiative will deliver, especially for strategic actions.
This could be direct revenue, cost savings, or efficiency gains. Projecting these helps justify the investment.""",
     "gemini_base_prompt": "If my 'Strategic Action' initiative [describe] is successful, what are potential direct/indirect revenue streams or quantifiable benefits I could project?",
     "ask_gemini": True}
]

# --- Helper Functions ---
def get_multiline_input(prompt_message):
    """Gets multiline input from the user, using Rich for the prompt.
    Input is terminated by a single dot '.' on a new line or by typing '--skip'.
    """
    console.print(prompt_message + " (Type '.' on a new line to finish; type '--skip' to leave empty):", style=f"bold {CLR_STEEL_BLUE}")
    lines = []
    while True:
        line = console.input()
        if line.strip() == '.': # Terminate if line is exactly a dot
            break
        if line.strip().lower() == '--skip':
            return ""
        lines.append(line)
    return "\n".join(lines)

def call_gemini_api(api_key_to_use, prompt_text):
    """Calls the Gemini API and returns the response text."""
    if not api_key_to_use:
        return "Error: Gemini API key not provided."
    try:
        genai.configure(api_key=api_key_to_use)
        model = genai.GenerativeModel(model_name="gemini-1.5-flash-latest")
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]
        response = model.generate_content(prompt_text, safety_settings=safety_settings)

        if response.parts:
            return response.text
        else:
            block_reason = "Unknown"
            safety_ratings_info = ""
            if response.prompt_feedback:
                block_reason = response.prompt_feedback.block_reason if response.prompt_feedback.block_reason else "Not specified"
                if response.prompt_feedback.safety_ratings:
                    safety_ratings_info = "\nSafety Ratings:"
                    for rating in response.prompt_feedback.safety_ratings:
                        safety_ratings_info += f"\n  - Category: {rating.category.name}, Probability: {rating.probability.name}"
            return f"Error: Gemini API call was successful but returned no content (potentially blocked). Reason: {block_reason}.{safety_ratings_info}"
    except Exception as e:
        return f"Error calling Gemini API: {e}"

def save_markdown_incrementally(output_path, current_user_inputs):
    """Generates and saves the Markdown content incrementally."""
    markdown_content = ""
    if current_user_inputs.get('main_title'):
        markdown_content += f"# {current_user_inputs['main_title']}\n\n"
    else:
        markdown_content += f"# MOTION Document (In Progress)\n\n"


    last_category = None
    for section_data in TEMPLATE_SECTIONS:
        section_id = section_data['id']
        if section_id == 'main_title':
            continue

        input_text = current_user_inputs.get(section_id, "").strip()
        category = section_data.get("category")

        if category and category != last_category:
            markdown_content += f"## {category}\n\n"
            last_category = category

        markdown_content += f"### {section_data['title']}\n"
        if input_text:
            markdown_content += f"{input_text}\n\n"
        else:
            markdown_content += f"_{section_data.get('description', 'Content to be provided.').strip().replace(chr(10), ' ')}_\n\n"

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        console.print(f"💾 Document updated: '[italic {CLR_CYAN}]{output_path}[/italic {CLR_CYAN}]'", style=f"dim {CLR_DIM_WHITE}")
    except IOError as e:
        console.print(f"❌ Error updating file '{output_path}'. Reason: {e}", style=f"bold {CLR_RED}")


# --- Main Script Logic ---
def generate_motion_document():
    global API_KEY
    global console

    console.rule(f"[bold {CLR_BRIGHT_MAGENTA}]MOTION Document Generator with Gemini AI[/bold {CLR_BRIGHT_MAGENTA}]", style=CLR_MAGENTA)

    motion_intro_text = textwrap.dedent("""
        **Welcome to the MOTION Document Generator!**

        A **MOTION** is an act or process of changing place or position.
        In our context, MOTION projects support the company strategy by fostering constant improvement.
        They serve as an entry point for personal initiatives, bridging the gap between bottom-up and top-down approaches.

        **Key aspects of MOTION initiatives include:**
        - **Ownership:** You are owners of the MOTION initiatives you are involved in.
        - **Interest:** Get involved in areas that genuinely interest you.
        - **Commitment:** Deliver quality comparable to client projects.
        - **Lab for Innovation:** MOTIONs act as a lab for process innovation.
        - **Knowledge Increase:** They support self-learning and industry knowledge growth.

        This script will guide you through structuring your MOTION proposal.
    """)
    console.print(Panel(Markdown(motion_intro_text), title=f"[bold {CLR_ORANGE}]Understanding MOTION Initiatives[/bold {CLR_ORANGE}]", border_style=CLR_ORANGE, expand=False, padding=(1,2)))

    console.print("This script will guide you through creating your document, using general proposal best practices,", style="italic")
    console.print(f"and using [bold]Gemini AI[/bold] as your sparring partner, with [bold]Markdown[/bold] rendering for advice", style="italic")
    console.print("and pickable JSON suggestions.", style="italic")
    console.print("---" * (console.width // 3), justify="center")

    home_dir = Path.home()
    current_date_str = datetime.now().strftime("%Y%m%d")
    default_filename = f"MOTION_PROPOSAL_{current_date_str}.md"
    default_save_path = home_dir / default_filename

    console.print(f"\n[bold {CLR_CYAN}]File Save Location[/bold {CLR_CYAN}]")
    console.print(f"The default location to save the file is: [italic]{default_save_path}[/italic]")
    user_save_path_str = console.input(f"Press Enter to accept, or type a new full path (e.g., /path/to/your/directory/{default_filename}): ").strip()

    output_path = None
    if not user_save_path_str:
        output_path = default_save_path
    else:
        try:
            output_path = Path(user_save_path_str)
            if output_path.is_dir():
                output_path = output_path / default_filename
            output_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            console.print(f"[bold {CLR_RED}]Error with provided path: {e}. Using default location.[/bold {CLR_RED}]")
            output_path = default_save_path
            output_path.parent.mkdir(parents=True, exist_ok=True)

    console.print(f"📝 Document will be saved as: [italic {CLR_CYAN}]{output_path}[/italic {CLR_CYAN}]")

    if not API_KEY:
        console.print("Your Gemini API key was not found as an environment variable ('GEMINI_API_KEY').", style=CLR_YELLOW)
        API_KEY = console.input(f"[bold {CLR_DEEP_SKY_BLUE}]Please enter your Gemini API key: [/bold {CLR_DEEP_SKY_BLUE}]").strip()
        if not API_KEY:
            console.print("No API key provided. Gemini integration will be disabled.", style=f"bold {CLR_RED}")
    else:
        console.print("Using Gemini API key from environment variable.", style=CLR_GREEN)

    user_inputs = {}
    initiative_context_for_gemini = ""

    save_markdown_incrementally(output_path, user_inputs)

    for section in TEMPLATE_SECTIONS:
        console.rule(f"[bold {CLR_SKY_BLUE}]SECTION: {section['title']}[/bold {CLR_SKY_BLUE}]", style=CLR_SKY_BLUE)
        if section.get('required'):
            console.print("(This section is Required)", style=f"bold {CLR_YELLOW}")

        if section.get('description'):
            console.print(Panel(Text(section['description'], justify="left"), title=f"[bold {CLR_DODGER_BLUE}]📋 Description from Template[/bold {CLR_DODGER_BLUE}]", border_style=CLR_DODGER_BLUE, expand=False, padding=(0,1)))

        console.print(Panel(Text(section['guidance'], justify="left"), title=f"[bold {CLR_PLUM}]💡 Guidance[/bold {CLR_PLUM}]", border_style=CLR_PLUM, expand=False, padding=(1,2)))

        console.print("---" * (console.width // 3), justify="center")
        user_initial_input = get_multiline_input(f"➡️ Enter your initial thoughts for '[italic]{section['title']}[/italic]'")
        user_inputs[section['id']] = user_initial_input

        if section['id'] == 'main_title' and user_initial_input:
            initiative_context_for_gemini = f"The overall initiative title/theme is: '{user_initial_input}'. "
        elif section['id'] == 'summary' and user_initial_input:
             initiative_context_for_gemini += f"The summary of the initiative is: '{user_initial_input}'. "

        action_taken_for_section_input = False

        if section.get("ask_gemini", True) and API_KEY:
            consult_gemini_choice = console.input(f"❓ Consult Gemini for '[italic]{section['title']}[/italic]'? (yes/no, default: [bold]yes[/bold]): ").strip().lower()
            if consult_gemini_choice != 'no':
                console.print(f"\n🤖 [bold]Consulting Gemini for '[italic]{section['title']}[/italic]'...[/bold]")

                json_format_instruction = (
                    "Your response MUST have two distinct parts:\n"
                    "PART 1: Your narrative critique, suggestions, and any probing questions in Markdown format. Focus on helping me strengthen this section based on its purpose and the provided guidance.\n"
                    "PART 2: A JSON object containing a list of specific, distinct, alternative phrasings or actionable suggestions for the content of this section. "
                    "These should be complete phrases or sentences that could be used directly or as strong starting points. "
                    "Format this JSON block exactly as follows, starting it with the exact delimiter ---JSON_START--- on its own line, and ending it with the exact delimiter ---JSON_END--- on its own line:\n"
                    "---JSON_START---\n"
                    "{\n"
                    "  \"suggestions\": [\n"
                    "    \"Complete suggested phrasing 1...\",\n"
                    "    \"Alternative complete phrasing 2...\",\n"
                    "    \"Another distinct idea or phrasing...\"\n"
                    "  ]\n"
                    "}\n"
                    "---JSON_END---\n"
                    "If you have no specific alternative phrasings to offer as a list for PART 2, provide an empty list in the JSON: {\"suggestions\": []}. "
                    "Ensure the JSON is valid and strictly follows this two-delimiter format. Your narrative response in PART 1 MUST come before the ---JSON_START--- delimiter."
                )

                api_prompt = (
                    f"You are an expert proposal writing coach and a helpful AI assistant.\n"
                    f"I am working on filling out the '{section['title']}' section for an innovation proposal document.\n"
                    f"{initiative_context_for_gemini}"
                    f"The general guidance for this section is: '{section['guidance']}'.\n\n"
                    f"My initial thoughts for this section are:\n'''\n{user_initial_input}\n'''\n\n"
                    f"{json_format_instruction}\n\n"
                    f"For PART 1 (your narrative advice), please focus on: {section['gemini_base_prompt'] if section['gemini_base_prompt'] else 'general improvements for this section based on the guidance and my input.'}"
                )

                with console.status(f"[bold {CLR_YELLOW}]Waiting for Gemini's wisdom...", spinner="dots"):
                    gemini_response_full = call_gemini_api(API_KEY, api_prompt)

                console.print(f"\n💬 [bold {CLR_CHARTREUSE}]Gemini's Response:[/bold {CLR_CHARTREUSE}]")

                narrative_response_md = ""
                parsed_suggestions_json = []
                json_error_message = None
                json_str_raw_for_error = ""

                if gemini_response_full and not gemini_response_full.startswith("Error:"):
                    try:
                        start_delimiter = "---JSON_START---"
                        end_delimiter = "---JSON_END---"

                        json_start_idx = gemini_response_full.find(start_delimiter)
                        json_end_idx = gemini_response_full.rfind(end_delimiter)

                        if json_start_idx != -1 and json_end_idx != -1 and json_start_idx < json_end_idx:
                            narrative_response_md = gemini_response_full[:json_start_idx].strip()
                            json_str_raw_for_error = gemini_response_full[json_start_idx + len(start_delimiter) : json_end_idx].strip()

                            parsed_data = json.loads(json_str_raw_for_error)
                            parsed_suggestions_json = parsed_data.get("suggestions", [])

                            if not isinstance(parsed_suggestions_json, list):
                                console.print(f"[italic {CLR_BRIGHT_RED}]Warning: 'suggestions' in JSON from Gemini was not a list. Treating as no suggestions.[/italic {CLR_BRIGHT_RED}]")
                                parsed_suggestions_json = []
                        else:
                            narrative_response_md = gemini_response_full
                            console.print(f"[italic {CLR_YELLOW}]JSON delimiters not found as expected in Gemini's response. Displaying full response as narrative.[/italic {CLR_YELLOW}]")

                    except json.JSONDecodeError as e:
                        json_error_message = f"Error decoding JSON from Gemini: {e}. Raw JSON string part: '{json_str_raw_for_error[:200]}...'"
                        narrative_response_md = gemini_response_full
                    except Exception as e:
                        json_error_message = f"Unexpected error processing Gemini response structure: {e}"
                        narrative_response_md = gemini_response_full

                    if narrative_response_md:
                        console.print(Panel(Markdown(narrative_response_md), title="[ai] Gemini AI - Narrative Advice", border_style=CLR_CHARTREUSE, expand=True, padding=(1,2)))
                    else:
                        console.print(f"[italic {CLR_YELLOW}]No narrative advice from Gemini, or an error occurred during its extraction.[/italic {CLR_YELLOW}]")

                    if json_error_message:
                        console.print(f"[{CLR_BRIGHT_RED}]{json_error_message}[/{CLR_BRIGHT_RED}]")

                    if parsed_suggestions_json:
                        console.print(f"\n[bold {CLR_MAGENTA}]Pickable Suggestions from Gemini (JSON):[/bold {CLR_MAGENTA}]")
                        for i, suggestion_text in enumerate(parsed_suggestions_json):
                            lines = suggestion_text.splitlines()
                            if lines:
                                console.print(f"  [bold {CLR_CYAN}][{i+1}] [/bold {CLR_CYAN}] {lines[0]}")
                                for line_num, line_content in enumerate(lines[1:]):
                                    console.print(f"        {line_content}")
                            elif suggestion_text:
                                console.print(f"  [bold {CLR_CYAN}][{i+1}] [/bold {CLR_CYAN}] {suggestion_text}")


                        console.print(f"\n[bold {CLR_GOLD}]Your Original Input for this section:[/bold {CLR_GOLD}]")
                        console.print(Panel(user_initial_input if user_initial_input else f"[italic {CLR_YELLOW}]No original input.[/italic {CLR_YELLOW}]", border_style=CLR_GOLD, padding=(0,1)))

                        while True:
                            console.print("\n[bold]How would you like to refine your answer?[/bold]")
                            console.print(f"  [key][o][/key] - Use your [bold {CLR_GOLD}]O[/bold {CLR_GOLD}]riginal input.")
                            console.print(f"  [key][t][/key] - [bold {CLR_STEEL_BLUE}]T[/bold {CLR_STEEL_BLUE}]ype a new/custom answer.")
                            console.print(f"  [key][p <nums>][/key] - [bold {CLR_CHARTREUSE}]P[/bold {CLR_CHARTREUSE}]ick suggestion(s) by number (e.g., 'p 1' or 'p 1,3').")
                            console.print(f"  [key][e <num>][/key] - [bold {CLR_ROYAL_BLUE}]E[/bold {CLR_ROYAL_BLUE}]dit a specific suggestion (e.g., 'e 2').")

                            choice_input = console.input("Your choice: ").strip().lower()
                            temp_section_input = None

                            if choice_input == 'o':
                                temp_section_input = user_initial_input
                                console.print(f"[dim {CLR_DIM_WHITE}]Original input selected.[/dim {CLR_DIM_WHITE}]")
                            elif choice_input == 't':
                                temp_section_input = get_multiline_input(f"➡️ Enter your new/custom content for '[italic]{section['title']}[/italic]'")
                            elif choice_input.startswith('p '):
                                try:
                                    nums_str = choice_input[2:].strip()
                                    if not nums_str: raise ValueError("No numbers provided for 'p'.")
                                    selected_indices = [int(n.strip()) - 1 for n in nums_str.split(',')]
                                    chosen_texts = []
                                    valid_selection = True
                                    for index in selected_indices:
                                        if 0 <= index < len(parsed_suggestions_json):
                                            chosen_texts.append(parsed_suggestions_json[index])
                                        else:
                                            console.print(f"[bold {CLR_BRIGHT_RED}]Error: Invalid suggestion number '{index+1}'.[/bold {CLR_BRIGHT_RED}]")
                                            valid_selection = False; break
                                    if valid_selection and chosen_texts:
                                        temp_section_input = "\n\n".join(chosen_texts)
                                        console.print(Panel(temp_section_input, title=f"[bold {CLR_CHARTREUSE}]Combined Suggestion(s) Selected[/bold {CLR_CHARTREUSE}]", border_style=CLR_CHARTREUSE, padding=(0,1)))
                                except ValueError as ve:
                                    console.print(f"[bold {CLR_BRIGHT_RED}]Error: {ve}. Use comma-separated numbers (e.g., 'p 1,3').[/bold {CLR_BRIGHT_RED}]")
                            elif choice_input.startswith('e '):
                                try:
                                    num_str = choice_input[2:].strip()
                                    if not num_str: raise ValueError("No number provided for 'e'.")
                                    idx_to_edit = int(num_str) - 1
                                    if 0 <= idx_to_edit < len(parsed_suggestions_json):
                                        selected_suggestion_text = parsed_suggestions_json[idx_to_edit]
                                        console.print(f"\n[bold {CLR_ROYAL_BLUE}]Starting point for your edit (Suggestion [{idx_to_edit+1}]):[/bold {CLR_ROYAL_BLUE}]")
                                        console.print(Panel(selected_suggestion_text, border_style=CLR_ROYAL_BLUE, padding=(0,1)))
                                        temp_section_input = get_multiline_input(f"➡️ Enter your edited version for '[italic]{section['title']}[/italic]' (based on suggestion [{idx_to_edit+1}])")
                                    else:
                                        console.print(f"[bold {CLR_BRIGHT_RED}]Error: Invalid suggestion number '{idx_to_edit+1}' for editing.[/bold {CLR_BRIGHT_RED}]")
                                except ValueError as ve:
                                    console.print(f"[bold {CLR_BRIGHT_RED}]Error: {ve}. Use a valid number (e.g., 'e 2').[/bold {CLR_BRIGHT_RED}]")
                            else:
                                console.print(f"[bold {CLR_BRIGHT_RED}]Invalid choice. Please try again.[/bold {CLR_BRIGHT_RED}]")

                            if temp_section_input is not None:
                                user_inputs[section['id']] = temp_section_input
                                action_taken_for_section_input = True
                                break
                    else:
                        if not json_error_message and gemini_response_full and not gemini_response_full.startswith("Error:"):
                            console.print(f"[italic {CLR_YELLOW}]Gemini provided no pickable JSON suggestions. You can refine your input based on the narrative advice.[/italic {CLR_YELLOW}]")
                        user_inputs[section['id']] = get_multiline_input(f"➡️ Enter your refined/final content for '[italic]{section['title']}[/italic]' (considering Gemini's narrative and your original input: '{user_initial_input[:50].replace(chr(10), ' ')}...')")
                        action_taken_for_section_input = True

                else:
                    if gemini_response_full and gemini_response_full.startswith("Error:"):
                        console.print(Panel(f"[italic {CLR_RED}]{gemini_response_full}[/italic {CLR_RED}]", title="[ai] Gemini Error", border_style=CLR_RED, expand=False, padding=(0,1)))

                    if not (consult_gemini_choice == 'no'):
                        user_inputs[section['id']] = get_multiline_input(f"➡️ Enter your content for '[italic]{section['title']}[/italic]' (Gemini consultation issue. Original input: '{user_initial_input[:50].replace(chr(10), ' ')}...')")
                    action_taken_for_section_input = True

            else:
                action_taken_for_section_input = True
                pass

        if not action_taken_for_section_input:
             user_inputs[section['id']] = user_initial_input

        save_markdown_incrementally(output_path, user_inputs)

        console.print("---" * (console.width // 3), justify="center")

    console.rule(f"[bold {CLR_BRIGHT_MAGENTA}]🎉 All sections complete! Final document generated. 🎉[/bold {CLR_BRIGHT_MAGENTA}]", style=CLR_MAGENTA)
    console.print(f"\n✅ Final document saved at '[bold {CLR_CYAN}]{output_path}[/bold {CLR_CYAN}]'!", style=f"bold {CLR_GREEN}")
    console.print("You can now open this Markdown file with any text editor or Markdown viewer.", style="italic")
    console.print("Remember to review and further refine your document.")


if __name__ == "__main__":
    if 'genai' not in globals():
        if 'console' in globals():
            console.print(f"Critical dependency 'google-generativeai' is missing. Please install it.", style=f"bold {CLR_RED}")
        else:
            print("Critical dependency 'google-generativeai' is missing. Please install it.")
    elif 'Console' not in globals():
         print("Critical dependency 'rich' is missing. Please install it.")
    else:
        generate_motion_document()
