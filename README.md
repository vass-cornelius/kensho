# kensho
A Mind Mirror, Not Just a Log

## Do you ever end your day with a dozen unfinished tasks looping in your head? 🧠🔁
It’s a real thing called the **Zeigarnik Effect**: our brains are wired to fixate on incomplete tasks, draining our mental energy long after we've logged off. The key to stopping the loop is closure.

I’ve been working on a simple command-line script to practice this. It's not just another logging tool—it's a habit for gaining mental clarity.

I'm calling it Kensho (見性), a term for the experience of "seeing one's true nature."

**The Philosophy: A Mind Mirror, Not Just a Log**

A fitness tracker doesn't make you fit, but it makes your fitness visible.

In the same way, Kensho doesn't do your work, but it makes your mind visible. It’s a mirror reflecting your daily patterns, friction points, and moments of real momentum.

## The Habit: 5 Minutes to End the Loop
This isn't meant to be a chore. It’s a simple performance habit, not a rigid ritual.

- 3 quick bullet lists at the end of your day.
- 5 minutes, max.
- Skip a day? No guilt. Just start again tomorrow.

## The Payoff: From Solo Insight to Team Velocity
While it begins as a tool for self-awareness, the benefits multiply when a team adopts the habit:

- Better standups: Everyone arrives already aligned.
- Fewer repeated investigations: A clear breadcrumb trail exists.
- More accurate retros: You track daily reality, not just filtered Jira tickets.

## And Then, Kensho Becomes Your Coach...
This is where the mirror talks back. Once a month, Kensho’s most powerful feature unlocks. Using the --monthly-summary command, it leverages the Gemini API to analyze all your logs and delivers a deep-dive report on your progress, patterns, and actionable advice for the month ahead.

Ready to stop the loop and get a clearer view of your work?

# Running the script
Just download the daily_logger.py and safe it into your home directory (or checkout this repo, adapt paths).

```bash
$~: python3 ~/daily_logger.py
```

## Usage information

```bash
usage: daily_logger.py [-h] [--sow | --eow | --monthly-summary [MONTH]]

A script for daily, weekly, and monthly logging and analysis.

optional arguments:
  -h, --help            show this help message and exit
  --sow                 Run the Start of Week (SOW) questions.
  --eow                 Run the End of Week (EOW) questions.
  --monthly-summary [MONTH]
                        Generate a summary for a specific month of the current year (e.g., 5 for May).
                        If no month number is given, summarizes the previous full month.
```


# ⚠️ Important Setup Steps
To use the AI summary feature, you'll need to do two things first:

1. Install the Google AI Python Library: Open your terminal and run the following command:

```Bash
pip3 install google-generativeai
```

2. Get and Set Your Gemini API Key:

* You can get a free API key from [Google AI Studio](https://aistudio.google.com/app/apikey)
* For security, it's best to set this key as an environment variable rather than putting it directly in the script. Open your terminal and run this command, replacing YOUR_API_KEY with the key you just obtained:

```Bash
export GEMINI_API_KEY="YOUR_API_KEY"
```

_Note_: You'll need to run this export command in every new terminal session, or add it to your shell's startup file (e.g., ~/.zshrc or ~/.bash_profile) to make it permanent.


Linux Users:
```Bash
echo 'export GEMINI_API_KEY="YOUR_API_KEY"'
echo 'alias daily="python3 ~/daily_logger.py"' >> ~/.bash_profile
source ~/.bash_profile
```

Mac-Users:
```zsh
echo 'export GEMINI_API_KEY="YOUR_API_KEY"'
echo 'alias daily="python3 ~/daily_logger.py"' >> ~/.zshrc
source ~/.zshrc
```
