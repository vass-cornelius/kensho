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
    def __init__(self, api_key: str, model_name: str = "gemini-3-pro-preview"):
        self.model_name = model_name
        self.client = genai.Client(api_key)

    def _call_llm(self, prompt: str, temp: float = 0.2, thinking: bool = False) -> str:
        """Stateless call to the API."""
        try:
            if thinking:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=genai.types.GenerateContentConfig(
                        temperature=temp
                    )
                )
            else:
                response = self.client.models.generate_content(
                    contents=prompt,
                    config=genai.types.GenerationConfig(
                        temperature=temp,
                        thinking_config=genai.types.ThinkingConfig(
                            thinking_level='low'
                        )
                    )
                )
            return response.text.strip()
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

        GOAL:
        {main_goal}

        TASK:
        Break this goal down into 5-10 sequential, atomic steps. The final step needs to be: "Draft the final report following the required template structure, populating each section with the derived data and formulating actionable recommendations."
        Return ONLY a raw JSON list of strings.

        Example: ["Research topic X", "Draft introduction", "Summarize key points"]
        """

        raw = self._call_llm(prompt, temp=0.1, thinking=True)
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
        
        **Input Tasks:**
        {tasks}
        
        **Instructions:**
        1. Analyze the cognitive load required for each task.
        2. Assign "A" or "B" to each task.
        3. Provide a brief 1-sentence rationale using terms like "formatting," "semantic inference," or "synthesis."
        
        **Output Format:**
        Return a valid JSON object with the key "classifications" containing a list of objects, each with "task_id" (0-x), "model" ("A" or "B"), and "rationale".
        """
        raw = self._call_llm(prompt_template, temp=0.0, thinking=True)

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

        CURRENT ATOMIC TASK: {task}

        CRITICAL CONSTRAINT: 
        Your response must allow for easy verification. 
        Structure your answer as:
        1. [Key Concept/Direct Answer]
        2. [Supporting Evidence]
        """


        for i in range(vote_count):
            # Vary temp to get diverse approaches
            if model['model'] == "A":
                res = self._call_llm(prompt_template, temp=0.1 + (i * 0.25), thinking=False)
            else:
                res = self._call_llm(prompt_template, temp=0.1 + (i * 0.25), thinking=True)
            candidates.append(res)

        # Shuffle candidates to prevent bias
        import random
        random.shuffle(candidates)

        # 2. The Judge
        judge_prompt = f"""
        ### ROLE
        You are a Quality Assurance Senior Editor. You are tasked with evaluating multiple potential responses to a complex task and selecting the single best one.
        I will provide you with a TASK and three CANDIDATE RESPONSES generated by different AI agents.
        
        ORIGINAL TASK: {task}

        ---
        CANDIDATE RESPONSES:
        <Response_A>
        {candidates[0]}
        </Response_A>

        <Response_B>
        {candidates[1]}
        </Response_B>

        <Response_C>
        {candidates[2]}
        </Response_C>
        ---

        EVALUATION CRITERIA:
        1. **Accuracy:** Does the response directly address the Atomic Task without hallucination?
        2. **Consistency:** Does it align with the "Context Provided"?
        3. **Clarity:** Is the writing concise and actionable?
        4. **Biases:** Do not favor longer responses solely for their length. Prioritize conciseness.

        VOTING INSTRUCTIONS
        1. Analyze the differences between A, B, and C.
        2. If two responses agree and one contradicts, heavily penalize the outlier (unless the outlier is obviously factually superior).
        3. Select the winner.
        4. Return ONLY the winning response (A, B, or C).
        """

        winner_idx = 0
        try:
            winner_raw = self._call_llm(judge_prompt, temp=0.0, thinking=False)
            if "B" in winner_raw: winner_idx = 1
            if "C" in winner_raw: winner_idx = 2

            print(f"   -> Option {winner_idx + 1} won the vote.")
        except Exception as e:
            # Fallback: If JSON fails, default to the first response or log error
            print(f"Voting failed: {e} - Defaulted to 1")

        return candidates[winner_idx]

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