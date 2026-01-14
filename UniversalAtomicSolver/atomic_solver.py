from google import genai
import json
import re
from typing import List, TypedDict, Literal

from UniversalAtomicSolver.problem_state import ProblemState
from UniversalAtomicSolver.universal_validator import UniversalValidator

class TaskClassification(TypedDict):
    task_id: int
    model: Literal['A', 'B']  # Restricts value to only "A" or "B"
    rationale: str

class RouterResponse(TypedDict):
    classifications: List[TaskClassification]

class AtomicSolver:
    def __init__(self, api_key: str, model_name: str = "gemini-3-flash-preview"):
        self.model_name = model_name
        self.client = genai.Client(api_key=api_key)

    def _call_llm(self, prompt: str, temp: float = 1.0, thinking: bool = False) -> str:
        """Stateless call to the API."""
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    temperature=temp,
                    thinking_config=genai.types.ThinkingConfig(
                        thinking_level='high' if thinking else 'low'
                    )
                )
            )

            # Manually extract text to avoid warning about non-text parts (like thought_signature)
            text_parts = []
            if response.candidates:
                for part in response.candidates[0].content.parts:
                    if part.text:
                        text_parts.append(part.text)
            return "".join(text_parts).strip()
        except Exception as e:
            return f"# API Error: {e}"

    # --- RULE 2: MICRO-LEVEL DECOMPOSITION ---
    def decompose(self, state: ProblemState, main_goal: str) -> List[str]:
        """
        Breaks the goal into atomic steps based on the mode.
        """
        print(f"⚡ Decomposing goal...")

        role = "Strategic Planner"

        prompt = f"""
        You are a {role}.
        {state.get_prompt_context()}

        <goal>
        {main_goal}
        </goal>

        <task>
        Break this goal down into 4 sequential, atomic steps. The final step needs to be: "Draft the final report following the required template structure, populating each section with the derived data and formulating actionable recommendations."
        Return ONLY a raw JSON list of strings.

        Example JSON Output: ["Research topic X", "Draft introduction", "Summarize key points", "Draft the final report following the required template structure, populating each section with the derived data and formulating actionable recommendations."]
        </task>
        """

        raw = self._call_llm(prompt, thinking=True)
        print(f"   -> Raw: {raw}")
        # Attempt to clean JSON
        clean_json = re.sub(r"```json|```", "", raw).strip()

        try:
            steps = json.loads(clean_json)
            print(f"   -> Steps: {steps}")
            return steps
        except json.JSONDecodeError:
            print("   -> Decomposition failed JSON parsing. Fallback to single step.")
            return [main_goal]

    # --- Based on the task, try to find out, if we should use the base model or the
    # thinking model.
    def choose_model(self, tasks: List[str]):
        """
        Find the best model for each task.
        """
        print(f"⚡ Setting up task-routing...")
        prompt_template = f"""
        You are an expert **LLM Orchestrator and Router**. Your goal is to analyze a list of prompt tasks and determine the most efficient model to execute them.
        
        **The Models:**
        * **Model A (Fast Model):** Best for syntactic tasks, formatting, simple information extraction, chronological sorting, and strict pattern matching. Use this for low-perplexity tasks where the answer is explicitly in the text.
        * **Model B (Thinking/Reasoning Model):** Best for semantic tasks, ambiguity resolution, complex synthesis, multi-step logic, calculating trends involving causality, and qualitative analysis. Use this for high-entropy tasks requiring "Chain of Thought" reasoning.
        
        <Input Tasks>
        {tasks}
        </Input Tasks>
        
        <Instructions>
        1. Analyze the cognitive load required for each task.
        2. Assign "A" or "B" to each task.
        3. Provide a brief 1-sentence rationale using terms like "formatting," "semantic inference," or "synthesis."
        </Instructions>
        
        <Output Format>
        Return a valid JSON object with the key "classifications" containing a list of objects, each with "task_id" (0-x), "model" ("A" or "B"), and "rationale".

        Example JSON Output: {"classifications": [{"task_id": 0, "model": "A", "rationale": "formatting"}, {"task_id": 1, "model": "B", "rationale": "semantic inference"}]}
        </Output Format>
        """
        raw = self._call_llm(prompt_template, thinking=True)

        # Attempt to clean JSON
        clean_json = re.sub(r"```json|```", "", raw).strip()
        steps: RouterResponse = json.loads(clean_json)
        return steps['classifications']

    # --- RULE 3: VOTING FOR CRITICAL STEPS ---
    def solve_step_with_voting(self, state: ProblemState, task: str, model: TaskClassification, vote_count: int = 3) -> str:
        """
        Generates N solutions in parallel, then uses a Judge model to pick the best.
        """
        print(f"🗳️  Voting on: '{task}' using Model {model['model']}")

        candidates = []

        # 1. Generate Candidates (Simulated Parallelism)
        prompt_template = f"""
        You are an Expert Solver.
        {state.get_prompt_context()}

        <CURRENT ATOMIC TASK>
        {task}
        </CURRENT ATOMIC TASK>

        <CONSTRAINT>
        Your response must allow for easy verification. 
        Structure your answer as:
         <Key Concept/Direct Answer />
         <Supporting Evidence />
        </CONSTRAINT>
        """


        for i in range(vote_count):
            # Vary temp to get diverse approaches
            if model['model'] == "A":
                res = self._call_llm(prompt_template, temp=1.0 + (i * 0.25), thinking=False)
            else:
                res = self._call_llm(prompt_template, temp=1.0 + (i * 0.25), thinking=True)
            candidates.append(res)

        # Shuffle candidates to prevent bias
        import random
        random.shuffle(candidates)

        # 2. The Judge
        judge_prompt = f"""
        <ROLE>
        You are a senior quality assurance expert. Your task is to evaluate several possible answers to a 
        complex task based on the following criteria and select the best one. I will provide you with a 
        complex task and three candidate answers generated by different AI agents.
        </ROLE>

        <CANDIDATE RESPONSES to-task="{task}">
            <Response_A>
            {candidates[0]}
            </Response_A>

            <Response_B>
            {candidates[1]}
            </Response_B>

            <Response_C>
            {candidates[2]}
            </Response_C>
        </CANDIDATE RESPONSES>

        <EVALUATION CRITERIA>
        1. **Accuracy:** Does the response directly address the task without hallucination?
        2. **Consistency:** Does it align with the "Context Provided"?
        3. **Clarity:** Is the writing concise and actionable?
        4. **Biases:** Do not favor longer responses solely for their length. Prioritize conciseness.
        </EVALUATION CRITERIA>

        <VOTING INSTRUCTIONS>
        1. Analyze the differences between A, B, and C.
        2. If two responses agree and one contradicts, heavily penalize the outlier, unless the outlier is obviously factually superior.
        3. Select the winner.
        </VOTING INSTRUCTIONS>

        <OUTPUT FORMAT>
        Return ONLY the winning <Key Concept/Direct Answer> response.
        </OUTPUT FORMAT>
        """

        winner_raw = self._call_llm(judge_prompt, thinking=False)

        # remove html tags
        winner_raw = re.sub(r"<.*?>", "", winner_raw)
        return winner_raw

    def run(self, goal: str, context: str = "") -> str:
        state = ProblemState(context=context)

        # 2. Decompose
        steps = self.decompose(state, goal)
        number_of_steps = len(steps)

        # find the best model for each step
        models = self.choose_model(steps)

        # 3. Execute State Machine
        for i, step in enumerate(steps):
            print(f"\n⚙️  Step {i + 1}/{len(steps)}: {step}")
            if i == steps[-1]:
                # activate final model for last step (report generation)
                self.model_name = "gemini-3-pro-preview"

            # Solve with Voting
            new_content = self.solve_step_with_voting(state=state, task=step, model=models[i])

            # Validate
            is_valid, msg = UniversalValidator.validate(new_content)

            if is_valid:
                print(f"   ✅ {msg}")
                # Append or Replace based on logic (Here we append for accumulation)
                if (i + 1) < number_of_steps:
                    state.solution_content += f"\n\n--- {step} ---\n{new_content}"
                else:
                    state.solution_content =  f"{new_content}"

                state.last_error = None
            else:
                print(f"   ❌ {msg}")
                state.last_error = msg
                # Basic self-correction loop
                print("   -> Attempting self-correction...")
                fix_prompt = f"Fix this error in the previous output: {msg}\nOutput: {new_content}"
                fixed_content = self._call_llm(fix_prompt)

                # Check fix
                if UniversalValidator.validate(fixed_content)[0]:
                    state.solution_content += "\n" + fixed_content
                    print("   ✅ Fix Accepted.")
                else:
                    print("   ❌ Fix Failed. Skipping step.")



        print(f"\n🎉 FINAL RESULT:\n")
        return state.solution_content